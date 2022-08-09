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
inside a cage. This is to be improved in the future. For now, only Docker, Podman, Local and Qubes executors are available.

> **Remark**: Only Docker, Local (`sign`, `publish` and `upload` stages only) and Qubes executors inside a Fedora AppVM have been used by the author for validating the current development.

## How-to

### Dependencies

Fedora:
```bash
$ sudo dnf install python3-packaging createrepo_c devscripts gpg qubes-gpg-split python3-pyyaml rpm docker python3-docker podman python3-podman reprepro python3-pathspec rpm-sign
```

Debian:
```bash
$ sudo apt install python3-packaging createrepo-c devscripts gpg qubes-gpg-split python3-yaml rpm docker python3-docker reprepro python3-pathspec
```

Install `mkmetalink`:

Install https://github.com/QubesOS/qubes-infrastructure-mirrors:
```bash
$ git clone https://github.com/QubesOS/qubes-infrastructure-mirrors
$ cd qubes-infrastructure-mirrors
$ sudo python3 setup.py build
$ sudo python3 setup.py install
```

> Remark: Verify commit signature before building it.

### Docker executor

You need to add `user` to `docker` group in order to avoid using `sudo`:
```
$ usermod -aG docker user
```
You may need to `sudo su user` to have this working in the current shell. You may add this group owner change into
`/rw/config/rc.local`.

In order to use the Docker executor, you need to build the image using the provided dockerfiles. Docker images are built
from `scratch` with `mock` chroot cache archive. The rational is to use only built-in distribution tool that take care of
verifying content and not third-party content like Docker images from external registries.

First, build Mock chroot according to your own configuration or use default ones provided. For example, to build a
Fedora 36 x86-64 mock chroot from scratch:
```bash
$ sudo mock --init --no-bootstrap-chroot --config-opts chroot_setup_cmd='install dnf @buildsys-build' -r fedora-36-x86_64
```
By default, it creates a `config.tar.gz` located at `/var/cache/mock/fedora-36-x86_64/root_cache/`. Second, you can build
the docker image:
```bash
$ docker build -f dockerfiles/fedora.Dockerfile -t qubes-builder-fedora /var/cache/mock/fedora-36-x86_64/root_cache/
```

In order to ease Docker image generation, a tool `generate-docker-image.sh` is provided under `tools` directory to perform
previous commands with proper clean of previous caches. It takes as input the Mock configuration file path or identifier.

For example, to build a Fedora 36 x86-86 docker image:
```bash
$ tools/generate-docker-image.sh fedora-36-x86_64
```
and you can use docker executor for building Qubes OS components.

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
Usage: qb [OPTIONS] COMMAND [ARGS]...

  Main CLI

Options:
  --verbose / --no-verbose  Output logs.
  --debug / --no-debug      Print full traceback on exception.
  --builder-conf TEXT       Path to configuration file (default: builder.yml).
  --artifacts-dir TEXT      Path to artifacts directory (default:
                            ./artifacts).
  --log-file TEXT           Path to log file to be created.
  -c, --component TEXT      Override component in configuration file (can be
                            repeated).
  -d, --distribution TEXT   Override distribution in configuration file (can
                            be repeated).
  -t, --template TEXT       Override template in configuration file (can be
                            repeated).
  -e, --executor TEXT       Override executor type in configuration file.
  --executor-option TEXT    Override executor options in configuration file
                            provided as "option=value" (can be repeated). For
                            example, --executor-option image="qubes-builder-
                            fedora:latest"
  --help                    Show this message and exit.

Commands:
  package     Package CLI
  template    Template CLI
  repository  Repository CLI
  config      Config CLI

Stages:
    fetch prep build post verify sign publish upload

Remark:
    The Qubes OS components are separated in two groups: standard and template
    components. Standard components will produce distributions packages and
    template components will produce template packages.
```

You may use the provided development `builder-devel.yml` configuration file under `example-configs` located as
`builder.yml` in the root of `qubes-builderv2` (like the legacy `qubes-builder`).

Artifacts can be found under `artifacts` directory:
```
artifacts/
├── components          <- Stage artifacts for each component version and distribution.
├── distfiles           <- Extra source files.
├── repository          <- Qubes local builder repository (metadata are generated each time inside cages).
├── repository-publish  <- Qubes OS repositories that are synced to {yum,deb,...}.qubes-os.org.
├── sources             <- Qubes components source.
└── templates           <- Template artifacts.
```

#### Package

You can start building the components defined in this devel configuration as:
```bash
$ ./qb package fetch prep build
```

If GPG is set up on your host, specify key and client to be used inside `builder.yml`. Then, you can test sign and
publish stages:
```bash
$ ./qb package sign publish
```

In this case, you may run simply
```bash
$ ./qb package all
```
for triggering the whole build process.

#### Template

Similarly, you can start building the templates defined in this devel configuration as:
```bash
$ ./qb template all
```

#### Repository

In order to publish to a specific repository or if you ignored publish stage, you can use repository command to create
a local repository tha is usable by distributions. For example, to publish only the `whonix-gateway-16` template:

```bash
./qb -t whonix-gateway-16 repository publish templates-community-testing
```

or simply, all templates provided in `builder.yml` into `templates-itl-testing`:

```bash
./qb repository publish templates-itl-testing
```

Similar commands are available for packages, for example
```bash
./qb -d host-fc32 -c core-qrexec repository publish current-testing
```

or

```bash
./qb repository publish unstable
```

It's not possible to publish packages into template repositories `templates-itl`, `templates-itl-testing`, 
`templates-community`, and `templates-community-testing`. The same stands for templates not being publishable into 
`current`, `current-testing`, `security-testing` and `unstable`. A built-in filter is made to enforce this behavior.

If you try to publish into a stable repository like `current`, `templates-itl` or `templates-community`, packages or
templates should have been pushed to a testing repository first for a minimum of five days. You can ignore this rule
by providing `--ignore-min-age` to `publish` command.

Please note that `publish` plugin will not allow publishing into a stable repository. This is only possible with
the `repository` command.

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

### .qubesbuilder

Top level keys:

  PACKAGE_SET
  PACKAGE_SET-DISTRIBUTION_NAME (= Qubes OS distribution)

Inside each top level, it defines what "plugins" will take as input. For example, RPM_SPEC_FILES or DEBIAN_BUILD_DIRS
concerns package builders. Having both PACKAGE_SET and PACKAGE_SET-DISTRIBUTION_NAME with common keys is up to the
plugin to know in which order to use or consider them. It allows defining general or per distro options. In the case
of SOURCE_COPY_IN, being the key defining what "source" plugin needs to do. All processing steps like reading a spec,
generating sources (with additional commands defined here) will be run thanks to an executor like Podman, DispVM, etc.
