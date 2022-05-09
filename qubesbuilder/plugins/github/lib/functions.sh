#!/bin/sh

###
### Common setup
###

# load list of qubes-builder instances
config_file="$HOME/.config/qubes-builder-github/builders.list"

# don't return anything; log it locally, just in case
mkdir -p "$HOME/builder-github-logs"
log_basename="$HOME/builder-github-logs/$(date +%s)-$$"
exec >>"${log_basename}.log" 2>&1

tmpdir=$(mktemp -d)
# setup cleanup
trap 'rm -rf $tmpdir' EXIT

###
### Common functions for qubes-builder-github scripts
###

# read clearsign-ed command from stdin, verify against keys in $1, then write
# it to the file pointed by $2.
#
# Optionally, $3 may contain a variable name where signer key fingerprint is set.
#
# The script will close stdin to be sure no other (untrusted) data is obtained.
read_stdin_command_and_verify_signature() {
    local_keyring_path="$1"
    local_output_file="$2"
    local_signer="$3"

    if ! [ -r "$local_keyring_path" ]; then
        echo "Keyring $local_keyring_path does not exist" >&2
        return 1
    fi

    if ! [ -d "$tmpdir" ]; then
        echo "Temporary dir $tmpdir does not exist" >&2
        return 1
    fi

    # this will read from standard input of the service, the data should be
    # considered untrusted
    tr -d '\r' | awk -b \
            -v in_command=0 \
            -v in_signature=0 \
            -v output_data="$tmpdir/untrusted_command.tmp" \
            -v output_sig="$tmpdir/untrusted_command.sig" \
            '
        /^-----BEGIN PGP SIGNED MESSAGE-----$/ {
            # skip first 3 lines (this one, hash declaration and empty line)
            in_command=4
        }
        /^-----BEGIN PGP SIGNATURE-----$/ {
            in_command=0
            in_signature=1
        }
        {
            if (in_command > 1) {
                in_command--
                next
            }
        }
        {
            if (in_command) print >output_data
            if (in_signature) print >output_sig
        }
        /^-----END PGP SIGNATURE-----$/ {
            in_signature=0
        }
    '

    # make sure we don't read anything else from stdin
    exec </dev/null

    if [ ! -r "$tmpdir/untrusted_command.tmp" ] || \
            [ ! -r "$tmpdir/untrusted_command.sig" ]; then
        echo "Missing parts of gpg signature" >&2
        exit 1
    fi

    # gpg --clearsign apparently ignore trailing newline while calculating hash. So
    # must do the same here for signature verification. This is stupid.
    head -c -1 "$tmpdir/untrusted_command.tmp" > "$tmpdir/untrusted_command"

    if ! gpgv2 --keyring "$local_keyring_path" \
            --status-fd=3 \
            "$tmpdir/untrusted_command.sig" \
            "$tmpdir/untrusted_command" \
            3>"$tmpdir/gpg-status"; then
        echo "Invalid signature" >&2
        exit 1
    fi

    # extract signer fingerprint
    if [ -n "$local_signer" ]; then
        eval "$local_signer"="$(grep -Po \
            '^\[GNUPG:\] VALIDSIG (([0-9A-F-]+ ){9}|)\K([0-9A-F]*)' \
            "$tmpdir/gpg-status")"
    fi
    rm -f "$tmpdir/gpg-status"

    # now, take the first line of already verified file
    head -n 1 "$tmpdir/untrusted_command" > "$local_output_file"
    # add trailing newline back
    echo "" >> "$local_output_file"

    # log the command
    printf "Command: " >&2
    cat "$local_output_file" >&2
}


# Execute command given in $1 for each configured builder instance, in
# parallel, but only one instance will be running in given builder instance
# (the command will be called with builder.lock held).
# The command will be called with 2 arguments:
#  - release name (like r3.2)
#  - builder instance path
execute_in_each_builder() {
    local_cmd="$1"

    # look for a builder instance(s) for this release
    IFS="="
    while read -r config_release_name builder_dir; do
        if ! [ -d "$builder_dir" ]; then
            continue
        fi

        # at this point it's important to have only one instance running (and no build
        # process running), so take a lock; also go into background, as this may take
        # some time
        (
            exec 9> "$builder_dir/builder.lock"
            flock -x 9

            # avoid surprises later in the code
            IFS=' '

            # don't read $config_file (stdin for 'while' loop) and also don't mix
            # the output
            exec >>"${log_basename}-${config_release_name}.log" 2>&1 </dev/null

            $local_cmd "$config_release_name" "$builder_dir"

        ) &

    done < "$config_file"
}

# get list of allowed distributions for given key, including template aliases
# if dom0 is allowed, put it at the end of the list
# Arguments:
# - builder dir
# - key fingerprint
get_allowed_dists() {
    local_builder_dir="$1"
    local_signer_fpr="$2"

    local_dists=$(MAKEFLAGS='' make -s -C "$local_builder_dir" \
            get-var \
            GET_VAR="ALLOWED_DISTS_$local_signer_fpr")

    # now, filter out those not configured in DISTS_VM
    # shellcheck disable=SC2016
    configured_dists=$(MAKEFLAGS='' make -s -C "$local_builder_dir" \
            TEMPLATE_ALIAS= \
            FILTERED_DISTS='$(filter $(DISTS_VM),$(ALLOWED_DISTS_'"$local_signer_fpr"'))' \
            get-var \
            GET_VAR=FILTERED_DISTS)
    if echo " $local_dists " | grep -q ' dom0 '; then
        echo "$configured_dists dom0"
    else
        echo "$configured_dists"
    fi
}
