Qubes OS Builder
===

This is the next generation of Qubes OS builder.

## Work in progress

We provide brief instructions in order to help people who want to start contributing to this work in progress.

The new Qubes OS builder leverage container or DispVM isolation to run every stage of a build process. From
fetching sources and actually building them, everything will be executed inside a `cage` (either DispVM or container) with
the help of what we call an `executor`. For every single command that needs to perform an action from sources 
for example, cloning and verifying Git sources,rendering a SPEC file, generate SRPM or Debian source packages, etc.,
a fresh and new cage will be used. It remains only the signing and publishing process being executed locally and not
inside a cage. This is to be improved in the future.

For now, only Docker, Podman, Local and Qubes executors are available. Only Docker, Local and Qubes executors
inside a Fedora/Debian AppVM have been used by the author for validating the current development.

## How-to

### Dependencies

Fedora:
```bash
$ sudo dnf install python3-packaging createrepo_c devscripts gpg qubes-gpg-split python3-pyyaml rpm docker python3-docker podman python3-podman reprepro
```

Debian:
```bash
$ sudo apt install python3-packaging createrepo-c devscripts gpg qubes-gpg-split python3-yaml rpm docker python3-docker reprepro
```

### Docker executor

You need to add `user` to `docker` group in order to avoid using `sudo`:
```
$ usermod -aG docker user
```
You may need to `sudo su user` to have this working in the current shell. You may add this group owner change into
`/rw/config/rc.local`.

In order to use the Docker executor, you need to build the image using the provided Dockerfile:
```bash
$ docker build -f dockerfiles/fedora.Dockerfile -t qubes-builder-fedora .
```

### Qubes executor

We assume that the default template chosen for building components inside a DispVM will be `fedora-35`. For that, install
in the template the following dependencies:

```bash
$ sudo dnf install -y createrepo_c debootstrap devscripts dpkg-dev git mock pbuilder which perl-Digest-MD5 perl-Digest-SHA python3-pyyaml python3-sh rpm-build rpmdevtools wget python3-debian reprepro systemd-udev
```

Then, clone default DispVM based on Fedora 35 `fedora-35-dvm` as `qubes-builder-dvm`. Set at least `30GB` for its
private volume.You need to install `rpc/qubesbuilder.FileCopyIn` and `rpc/qubesbuilder.FileCopyOut` in
`qubes-builder-dvm` at location `/usr/local/etc/qubes-rpc`.

Assuming that your qube hosting `qubes-builder` is called `work-qubesos` (else you need to adjust policies), in `dom0`,
copy `rpc/policy/50-qubesbuilder.policy` to `/etc/qubes/policy.d`.

Now, start the disposable template `qubes-builder-dvm` and create the following directories:
```bash
$ sudo mkdir -p /rw/bind-dirs/builder /rw/config/qubes-bind-dirs.d
```

Create the file `/rw/config/qubes-bind-dirs.d/builder.conf` with content:
```
binds+=('/builder')
```

Append to `/rw/config/rc.local` the following:
```
mount /builder -o dev,suid,remount
```

Set default DispVM of `work-qubesos` being `qubes-builder-dvm`:
```bash
$ qvm-prefs work-qubesos default_dispvm qubes-builder-dvm
```

### Build stages

The whole build process occurs during those ordered stages:

- fetch
- prep
- build
- post
- verify
- sign
- publish

Currently, only those are used:

- fetch (downloading and verify sources)
- prep (creating source packages)
- build (building source packages)
- sign (signing built packages)
- publish (publishing signed packages)

### CLI

```bash
Usage: qb [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...

Options:
  --verbose / --no-verbose  Output logs.
  --debug / --no-debug      Print full traceback on exception.
  --builder-conf PATH       Path to configuration file (default: builder.yml)
  -c, --component TEXT      Override component in configuration file (can be repeated).
  -d, --distribution TEXT   Override distribution in configuration file (can be repeated).
  --help                    Show this message and exit.

Commands:
  build
  fetch
  post
  prep
  publish
  sign
  verify
```

You may use the provided development `builder-devel.yml` configuration file under `example-configs` located as
`builder.yml` in the root of `qubes-builderv2` (like the legacy `qubes-builder`).

You can start building the components defined in this devel configuration as:
```bash
$ ./qb fetch prep build
```

If GPG is setup on your host, specify key and client to be used inside `builder.yml`. Then, you can test sign and 
publish stages:
```bash
$ ./qb sign publish
```

Artifacts can be found under `artifacts` directory:
```
artifacts/
├── components          <- Stage artifacts for each component version and distribution.
├── distfiles           <- Extra source files.
├── repository          <- Qubes local builder repository (metadata are generated each time inside cages).
├── repository-publish  <- Qubes OS repositories that are synced to {yum,deb,...}.qubes-os.org.
└── sources             <- Qubes component source.
```

### Signing with Split GPG

If you plan to sign packages with Split GPG, don't forget to add to your `~/.rpmmacros`:
```
%__gpg /usr/bin/qubes-gpg-client-wrapper

%__gpg_check_password_cmd   %{__gpg} \
        gpg --batch --no-verbose -u "%{_gpg_name}" -s

%__gpg_sign_cmd /bin/sh sh -c '/usr/bin/qubes-gpg-client-wrapper \\\
        --batch --no-verbose \\\
        %{?_gpg_digest_algo:--digest-algo %{_gpg_digest_algo}} \\\
        -u "%{_gpg_name}" -sb %{__plaintext_filename} >%{__signature_filename}'
```
