#!/bin/bash
# vim: set ts=4 sw=4 sts=4 et :

set -e

VERBOSE=${VERBOSE:-1}
DEBUG=${DEBUG:-0}

# ------------------------------------------------------------------------------
# Run a command inside chroot
# ------------------------------------------------------------------------------
if [ "0${VERBOSE}" -ge 2 ] || [ "${DEBUG}" == "1" ]; then
    chroot_cmd() {
        local retval
        # Need to capture exit code after running chroot or systemd-nspawn
        # so it will be available as a return value
        # shellcheck disable=SC2015
        if [ "${SYSTEMD_NSPAWN_ENABLE}"  == "1" ]; then
            systemd-nspawn -D "${INSTALL_DIR}" -M "${DIST}" ${1+"$@"} && { retval=$?; true; } || { retval=$?; true; }
        else
            /usr/sbin/chroot "${INSTALL_DIR}" ${1+"$@"} && { retval=$?; true; } || { retval=$?; true; }
        fi
        return $retval
    }
else
    chroot_cmd() {
        if [ "${SYSTEMD_NSPAWN_ENABLE}"  == "1" ]; then
            systemd-nspawn -D "${INSTALL_DIR}" -M "${DIST}" ${1+"$@"}
        else
            /usr/sbin/chroot "${INSTALL_DIR}" ${1+"$@"}
        fi
    }
fi

# ------------------------------------------------------------------------------
# Display messages
# ------------------------------------------------------------------------------
# Only output text under certain conditions
output() {
    if [ "0${VERBOSE}" -ge 1 ] && [[ -z ${TEST} ]]; then
        # Don't echo if -x is set since it will already be displayed via true
        [[ ${-/x} != "$-" ]] || echo -e "$@"
    fi
}

info() {
    output "INFO: $*" || :
}

debug() {
    output "DEBUG: $*" || :
}

warn() {
    output "WARNING: $*" || :
}

error() {
    output "ERROR: $*" || :
}

# ------------------------------------------------------------------------------
# Return file or directory for current flavor.
#
# Example:
#   resource = packages.list
#
# Will look for a file name or directory matching the first occurrence:
#  - packages_${DIST_NAME}_{DIST_VER}_${TEMPLATE_FLAVOR}.list
#  - packages_${DIST_NAME}_${TEMPLATE_FLAVOR}.list
#  - packages_${DIST_NAME}.list
#
# Remark: If 'resource' is provided with full path, we use
#  its dirname as search directory instead of TEMPLATE_CONTENT_DIR.
# ------------------------------------------------------------------------------
get_file_or_directory_for_current_flavor() {
    local resource="$1"
    local suffix="$2"
    local resource_dir
    local ext

    # If 'resource' is provided with full path
    # we use its dirname as search directory
    # instead of TEMPLATE_CONTENT_DIR
    if [ "$(dirname "${resource}")" != "." ]; then
        resource_dir="$(dirname "${resource}")"
        resource="$(basename "${resource}")"
    else
        resource_dir="${TEMPLATE_CONTENT_DIR}"
    fi

    # Determine if resource has an extension. If it has,
    # we save this extension and we strip it from 'resource'.
    if [ "${resource##*.}" != "${resource}" ]; then
        ext=".${resource##*.}"
        resource_without_ext="${resource%.*}"
    else
        ext=""
        resource_without_ext="${resource}"
    fi
    # shellcheck disable=SC2153
    if [ -n "${suffix}" ] && [ -e "${resource_dir}/${resource_without_ext}_${suffix}${ext}" ]; then
        file_or_directory="${resource_dir}/${resource_without_ext}_${suffix}${ext}"
    elif [ -e "${resource_dir}/${resource_without_ext}_${DIST_CODENAME}_${TEMPLATE_FLAVOR}${ext}" ]; then
        file_or_directory="${resource_dir}/${resource_without_ext}_${DIST_CODENAME}_${TEMPLATE_FLAVOR}${ext}"
    elif [ -e "${resource_dir}/${resource_without_ext}_${DIST_CODENAME}${ext}" ]; then
        file_or_directory="${resource_dir}/${resource_without_ext}_${DIST_CODENAME}${ext}"
    elif [ -e "${resource_dir}/${resource_without_ext}_${DIST_NAME}_${DIST_VER}_${TEMPLATE_FLAVOR}${ext}" ]; then
        file_or_directory="${resource_dir}/${resource_without_ext}_${DIST_NAME}_${DIST_VER}_${TEMPLATE_FLAVOR}${ext}"
    elif [ -e "${resource_dir}/${resource_without_ext}_${DIST_NAME}_${TEMPLATE_FLAVOR}${ext}" ]; then
        file_or_directory="${resource_dir}/${resource_without_ext}_${DIST_NAME}_${TEMPLATE_FLAVOR}${ext}"
    elif [ -e "${resource_dir}/${resource_without_ext}_${DIST_NAME}${ext}" ]; then
        file_or_directory="${resource_dir}/${resource_without_ext}_${DIST_NAME}${ext}"
    else
        file_or_directory=""
    fi
    echo "${file_or_directory}"
}

containsFlavor() {
    flavor="${1}"
    retval=1
    local template_options

    # shellcheck disable=SC2153
    read -r -a template_options <<<"${TEMPLATE_OPTIONS[@]}"

    # Check the template flavor first
    if [ "${flavor}" == "${TEMPLATE_FLAVOR}" ]; then
        retval=0
    fi

    # Check the template flavors next
    elementIn "${flavor}" "${template_options[@]}" && {
        retval=0
    }

    return ${retval}
}

templateFlavorPrefix() {
    local template_flavor=${1-${TEMPLATE_FLAVOR}}
    local template_flavor_prefix
    # shellcheck disable=SC2153
    read -r -a template_flavor_prefix <<<"${TEMPLATE_FLAVOR_PREFIX[@]}"

    for element in "${template_flavor_prefix[@]}"
    do
        if [ "${element%:*}" == "${DIST}+${template_flavor}" ]; then
            echo "${element#*:}"
            return
        fi
    done

    # If template_flavor only contains a '+'; send back $DIST
    if [ "${template_flavor}" == "+" ]; then
        echo "${DIST}"
    else
        echo "${DIST}${template_flavor:++}"
    fi
}

templateNameFixLength() {
    local template_name="${1}"
    local temp_name
    read -r -a temp_name <<<"${template_name//+/ }"
    local index=$(( ${#temp_name[@]}-1 ))

    while [ ${#template_name} -ge 32 ]; do
        template_name=$(printf '%s' "${temp_name[0]}")
        if [ $index -gt 0 ]; then
            template_name+=$(printf '+%s' "${temp_name[@]:1:index}")
        fi
        (( index-- ))
        if [ $index -lt 1 ]; then
            template_name="${template_name:0:31}"
        fi
    done

    echo "${template_name}"
}

templateNameDist() {
    local dist_name="${1}"
    template_name="$(templateName)" && dist_name="${template_name}"

    # Automaticly correct name length if it's greater than 32 chars
    dist_name="$(templateNameFixLength "${dist_name}")"

    # Remove and '+' characters from name since they are invalid for name
    dist_name="${dist_name//+/-}"
    echo "${dist_name}"
}

templateName() {
    local template_flavor=${1:-${TEMPLATE_FLAVOR}}
    local template_name
    local template_options
    local template_label
    local template_options_concatenated
    retval=1 # Default is 1; mean no replace happened

    read -r -a template_options <<< "${TEMPLATE_OPTIONS[@]}"

    # Only apply options if $1 was not passed
    if [ -n "${1}" ] || [ -z "${TEMPLATE_OPTIONS[*]}" ]; then
        template_options_concatenated=
    else
        template_options_concatenated=$(printf '+%s' "${template_options[@]}")
    fi

    template_name="$(templateFlavorPrefix "${template_flavor}")${template_flavor}${template_options_concatenated}"

    # shellcheck disable=SC2153
    read -r -a template_label <<<"${TEMPLATE_LABEL[@]}"

    for element in "${template_label[@]}"; do
        if [ "${element%:*}" == "${template_name}" ]; then
            template_name="${element#*:}"
            retval=0
            break
        fi
    done

    # shellcheck disable=SC2005
    echo "$(templateNameFixLength "${template_name}")"
    return $retval
}


# ------------------------------------------------------------------------------
# Takes an array and exports it a global variable
#
# $1: Array to export
# $2: Global variable name to use for export
#
# http://ihaveabackup.net/2012/01/29/a-workaround-for-passing-arrays-in-bash/
#
# ------------------------------------------------------------------------------
setArrayAsGlobal() {
    local array="$1"
    local export_as="$2"
    local code
    local replaced
    code=$(declare -p "$array" 2> /dev/null || true)
    replaced="${code/$array/$export_as}"
    eval "${replaced/declare -/declare -g}"
}


# ------------------------------------------------------------------------------
# Checks if the passed element exists in passed array
# $1: Element to check for
# $2: Array to check for element in
#
# Returns 0 if True, or 1 if False
# ------------------------------------------------------------------------------
elementIn () {
  local element
  for element in "${@:2}"; do [[ "$element" == "$1" ]] && return 0; done
  return 1
}

# ------------------------------------------------------------------------------
# Splits the path and returns an array of parts
#
# $1: Full path of file to split
# $2: Global variable name to use for export
# Returns:
# ([full]='original name' [dir]='directory' [base]='filename' [ext]='extension')
#
# Original concept path split from:
# https://stackoverflow.com/questions/965053/extract-filename-and-extension-in-bash
#
# ------------------------------------------------------------------------------
splitPath() {

    local return_global_var=$2
    local filename="${1##*/}"                  # Strip longest match of */ from start
    local dir="${1:0:${#1} - ${#filename}}"    # Substring from 0 through pos of filename
    local base="${filename%.[^.]*}"            # Strip shortest match of . plus at least one non-dot char from end
    local ext="${filename:${#base} + 1}"       # Substring from len of base through end
    if [ "$ext" ]; then
        local dotext=".$ext"
    else
        local dotext=""
    fi
    if [[ -z "$base" && -n "$ext" ]]; then     # If we have an extension and no base, it's really the base
        base=".$ext"
        ext=""
        dotext=""
    fi
    # shellcheck disable=SC2034
    declare -A PARTS=([full]="$1" [dir]="$dir" [base]="$base" [ext]="$ext" [dotext]="$dotext")
    setArrayAsGlobal PARTS "$return_global_var"
}

templateDirs() {
    local template_flavor=${1-${TEMPLATE_FLAVOR}}
    local template_flavor_prefix
    local template_flavor_dir
    local match=0

    # shellcheck disable=SC2153
    read -r -a template_flavor_dir <<<"${TEMPLATE_FLAVOR_DIR[@]}"

    for element in "${template_flavor_dir[@]}"
    do
        # (wheezy+whonix-gateway / wheezy+whonix-gateway+gnome[+++] / wheezy+gnome )
        if [ "${element%:*}" == "$(templateName "${template_flavor}")" ]; then
            eval echo -e "${element#*:}"
            match=1

        # Very short name compare (+proxy)
        elif [ "${element:0:1}" == "+" ] && [ "${element%:*}" == "+${template_flavor}" ]; then
            eval echo -e "${element#*:}"
            match=1

        # Generic template directory that matches all flavors, or even no flavors
        elif [ "${element:0:1}" == "*" ]; then
            eval echo -e "${element#*:}"
            match=1
        fi
    done

    if [ "${match}" -eq 1 ]; then
        return
    fi

    template_flavor_prefix="$(templateFlavorPrefix "${template_flavor}")"
    if [ -n "${template_flavor}" ] && [ "${template_flavor}" == "+" ]; then
        local dir="${TEMPLATE_CONTENT_DIR}/${template_flavor_prefix}"
    elif [ -n "${template_flavor}" ]; then
        local dir="${TEMPLATE_CONTENT_DIR}/${template_flavor_prefix}${template_flavor}"
    else
        local dir="${TEMPLATE_CONTENT_DIR}"
    fi

    echo "${dir}"
}

exists() {
    filename="${1}"

    if [ -e "${filename}" ] && ! elementIn "${filename}" "${GLOBAL_CACHE[@]}"; then
        # Cache $script
        #
        # GLOBAL_CACHE is declared in the `getFileLocations` function and is later
        # renamed to a name passed into the function as $1 to allow scripts using
        # the function to have access to the array
        GLOBAL_CACHE["${#GLOBAL_CACHE[@]}"]="${filename}"
        return 0
    fi
    return 1
}

templateFile() {
    local file="$1"
    local suffix="$2"
    local template_flavor="$3"
    local template_dirs

    template_dirs="$(templateDirs "${template_flavor}")"

    splitPath "${file}" path_parts

    for template_dir in "${template_dirs[@]}"; do
        # No template flavor
        if [ -z "${template_flavor}" ]; then
            if [ -n "${suffix}" ]; then
                # shellcheck disable=SC2154
                exists "${TEMPLATE_CONTENT_DIR}/${path_parts[base]}_${suffix}${path_parts[dotext]}" || true
            else
                exists "${TEMPLATE_CONTENT_DIR}/${path_parts[base]}${path_parts[dotext]}" || true
            fi
            return
        fi

        # Locate file in directory named after flavor
        if [ -n "${suffix}" ]; then
            # Append suffix to filename (before extension)
            # `minimal` is the template_flavor being used in comment example

            # (TEMPLATE_FLAVOR_DIR/minimal/packages_qubes_suffix.list)
            exists "${template_dir}/${template_flavor}/${path_parts[base]}_${suffix}${path_parts[dotext]}" || true

            # (TEMPLATE_FLAVOR_DIR/minimal/packages_qubes_suffix.list)
            exists "${template_dir}/${template_flavor}/${path_parts[base]}_${suffix}${path_parts[dotext]}" || true

            # (TEMPLATE_FLAVOR_DIR/packages_qubes_suffix.list)
            exists "${template_dir}/${path_parts[base]}_${suffix}${path_parts[dotext]}" || true

            # (TEMPLATE_FLAVOR_DIR/packages_qubes_minimal_suffix.list)
            exists "${template_dir}/${path_parts[base]}_${suffix}_${template_flavor}${path_parts[dotext]}" || true

            # (TEMPLATE_CONTENT_DIR/packages_qubes_minimal_suffix.list)
            exists "${TEMPLATE_CONTENT_DIR}/${path_parts[base]}_${suffix}_${template_flavor}${path_parts[dotext]}" || true
        else
            # (TEMPLATE_FLAVOR_DIR/minimal/packages_qubes.list)
            exists "${template_dir}/${template_flavor}/${path_parts[base]}${path_parts[dotext]}" || true

            # (TEMPLATE_FLAVOR_DIR/minimal/packages_qubes_minimal.list)
            exists "${template_dir}/${template_flavor}/${path_parts[base]}_${template_flavor}${path_parts[dotext]}" || true

            # (TEMPLATE_FLAVOR_DIR/packages_qubes.list)
            exists "${template_dir}/${path_parts[base]}${path_parts[dotext]}" || true

            # (TEMPLATE_FLAVOR_DIR/packages_qubes_minimal.list)
            exists "${template_dir}/${path_parts[base]}_${template_flavor}${path_parts[dotext]}" || true

            # (TEMPLATE_CONTENT_DIR/packages_qubes_minimal.list)
            exists "${TEMPLATE_CONTENT_DIR}/${path_parts[base]}_${template_flavor}${path_parts[dotext]}" || true
        fi
    done
}

copyTreeExec() {
    local source_dir="$1"
    local dir="$2"
    local template_flavor="$3"
    local target_dir="$4"
    local template_dirs

    template_dirs="$(templateDirs "${template_flavor}")"

    for template_dir in "${template_dirs[@]}"; do
        local source_dir
        local target_dir

        source_dir="$(readlink -m "${source_dir:-${template_dir}}/${dir}")"
        target_dir="$(readlink -m "${target_dir:-${INSTALL_DIR}}")"

        if ! [ -d "${source_dir}" ]; then
            debug "No extra files to copy for ${dir}"
            return 0
        fi

        debug "Copying ${source_dir}/* ${target_dir}"
        cp -rp "${source_dir}/." "${target_dir}"

        if [ -f "${source_dir}/.facl" ]; then
            debug "Restoring file permissions..."
            pushd "${target_dir}"
            {
                setfacl --restore="${source_dir}/.facl" 2>/dev/null ||:
                rm -f .facl
            }
            popd
        fi
    done
}

callTemplateFunction() {
    local calling_script="$1"
    local calling_arg="$2"
    local functionExec="$3"
    local template_flavor="${TEMPLATE_FLAVOR}"
    local template_options

    ${functionExec} "${calling_script}" \
                    "${calling_arg}" \
                    "${template_flavor}"

    # Find a $DIST sub-directory
    ${functionExec} "${calling_script}" \
                    "${calling_arg}" \
                    "+"

    read -r -a template_options <<<"${TEMPLATE_OPTIONS[@]}"

    for option in "${template_options[@]}"
    do
        # Long name (wheezy+whonix-gateway+proxy)
        ${functionExec} "${calling_script}" \
                        "${calling_arg}" \
                        "${TEMPLATE_FLAVOR}+${option}"

        # Short name (wheezy+proxy)
        ${functionExec} "${calling_script}" \
                        "${calling_arg}" \
                        "${option}"
    done

    # If template_flavor exists, also check on base distro
    if [ -n "${template_flavor}" ]; then
        ${functionExec} "${calling_script}" \
                        "${calling_arg}"
    fi
}

# ------------------------------------------------------------------------------
# Will return all files that match pattern of suffix
# Example:
#   filename = packages.list
#   suffix = ${DIST} (wheezy)
#
# Will look for a file name packages_wheezy.list in:
#   the $TEMPLATE_CONTENT_DIR; beside original
#   the $TEMPLATE_CONTENT_DIR/$DIST (wheezy) directory
#   any included template module directories ($TEMPLATE_CONTENT_DIR/gnome)
#
# All matches are returned and each will be able to be used
# ------------------------------------------------------------------------------
getFileLocations() {
    local return_global_var=$1
    local filename="$2"
    local suffix="$3"
    local function="templateFile"

    unset GLOBAL_CACHE
    declare -gA GLOBAL_CACHE

    callTemplateFunction "${filename}" "${suffix}" "${function}"
    setArrayAsGlobal GLOBAL_CACHE "$return_global_var"

    if [ ! ${#GLOBAL_CACHE[@]} -eq 0 ]; then
        debug "Smart files located for: '${filename##*/}' (suffix: ${suffix}):"
        for filename in "${GLOBAL_CACHE[@]}"; do
            debug "${filename}"
        done
    fi
}

# ------------------------------------------------------------------------------
# Executes any additional optional configuration steps if the configuration
# scripts exist
#
# Will find all scripts with
# Example:
#   filename = 04_install_qubes.sh
#   suffix = post
#
# Will look for a file name 04_install_qubes_post in:
#   the $TEMPLATE_CONTENT_DIR; beside original
#   the $TEMPLATE_CONTENT_DIR/$DIST (wheezy) directory
#   any included template module directories ($TEMPLATE_CONTENT_DIR/gnome)
#
# All matches are executed
# ------------------------------------------------------------------------------
buildStep() {
    local filename="$1"
    local suffix="$2"
    unset build_step_files

    info "Locating buildStep files: ${filename##*/} suffix: ${suffix}"
    getFileLocations "build_step_files" "${filename}" "${suffix}"

    # shellcheck disable=SC2154
    for script in "${build_step_files[@]}"; do
        if [ "${script}" == "${filename}" ]; then
            error "Recursion detected!"
            exit 1
        fi
        if [ -e "${script}" ]; then
            # Test module expects raw  output back only used to asser test results
            if [[ -n ${TEST} ]]; then
                echo "${script}"
            else
                info "Currently running script: ${script}"
            fi
            # Execute $script
            "${script}"
        fi
    done
}

# ------------------------------------------------------------------------------
# Copy extra file tree to ${INSTALL_DIR²}
# TODO:  Allow copy per step (04_install_qubes.sh-files)
#
# To set file permissions is a PITA since git won't save them and will
# complain heavily if they are set to root only read, so this is the procdure:
#
# 1. Change to the directory that you want to have file permissions retained
# 2. Change all the file permissions / ownership as you want
# 3. Change back to the root of the exta directory (IE: extra-qubes-files)
# 4. Manually restore facl's: setfacl --restore=.facl
# 5. Manually create facl backup used after copying: getfacl -R . > .facl
# 6. If git complains; reset file ownership back to user.  The .facl file stored
#    the file permissions and will be used to reset the file permissions after
#    they get copied over to ${INSTALL_DIR}
# NOTE: Don't forget to redo this process if you add -OR- remove files
# ------------------------------------------------------------------------------
copyTree() {
    local dir="$1"
    local source_dir="$2"
    local target_dir="$3"
    local function="copyTreeExec"

    if [ -z "${source_dir}" ]; then
        splitPath "${0}" path_parts
        if [ -d "${path_parts[dir]}/${dir}" ]; then
            copyTreeExec "${path_parts[dir]}" "${dir}" "" ""
        else
            callTemplateFunction "" "${dir}" "${function}"
        fi
    else
        copyTreeExec "${source_dir}" "${dir}" "" "${target_dir}"
    fi
}

# $0 is module that sourced vars.sh
info "Currently running script: ${0}"
