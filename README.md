# Qubes OS Builder

This is the second generation of the Qubes OS builder. This new builder
leverages container or disposable qube isolation to perform every stage of the
build and release process. From fetching sources to building them, everything
is executed inside a "cage" (either a disposable or a container) with the
help of what we call an "executor." For every command that needs to perform an
action on sources, like cloning and verifying Git repos, rendering a SPEC file,
generating SRPM or Debian source packages, a new cage is used. Only the
signing, publishing, and uploading processes are executed locally outside a
cage. (This will be improved in the future.) For now, only Docker, Podman,
Local, and Qubes executors are available.


## Dependencies

Fedora:

```bash
$ sudo dnf install python3-packaging createrepo_c devscripts gpg qubes-gpg-split python3-pyyaml rpm docker python3-docker podman python3-podman reprepro python3-pathspec rpm-sign mktorrent openssl tree
```

Debian:

```bash
$ sudo apt install python3-packaging createrepo-c devscripts gpg qubes-gpg-split python3-yaml rpm docker python3-docker reprepro python3-pathspec mktorrent openssl tree python3-setuptools python3-lxml
```

Install `mkmetalink`:

Install <https://github.com/QubesOS/qubes-infrastructure-mirrors>:

```bash
$ git clone https://github.com/QubesOS/qubes-infrastructure-mirrors
$ cd qubes-infrastructure-mirrors
$ sudo python3 setup.py build
$ sudo python3 setup.py install
```

**Note:** [Verify commit PGP
signatures](https://www.qubes-os.org/security/verifying-signatures/#how-to-verify-signatures-on-git-repository-tags-and-commits)
before building.


## Docker executor

Add `user` to the `docker` group if you wish to avoid using `sudo`:

```
$ usermod -aG docker user
```

You may need to `sudo su user` to get this to work in the current shell. You
can add this group owner change to `/rw/config/rc.local`.

In order to use the Docker executor, you must build the image using the
provided dockerfiles. Docker images are built from `scratch` with `mock`
chroot cache archive. The rational is to use only built-in distribution
tool that take care of verifying content and not third-party content
like Docker images from external registries. As this may not be possible
under Debian as build host, we allow to pull Fedora docker image with
a specific sha256.

In order to ease Docker or Podman image generation, a tool `generate-container-image.sh`
is provided under `tools` directory. It takes as input container engine
and optionally the Mock configuration file path or identifier.

For example, to build a Fedora 36 x86-64 docker image with `mock`:
```bash
$ tools/generate-container-image.sh docker fedora-36-x86_64
```
or a Podman image:
```bash
$ tools/generate-container-image.sh podman fedora-36-x86_64
```

If not specifying the `mock` configuration, it will simply build the
docker image based on the Fedora docker image.

### Detailed steps for Mock

You may want to customize your `mock` build process instead of using `generate-container-image.sh`.

First, build Mock chroot according to your own configuration or use 
default ones provided. For example, to build a Fedora 36 x86-64 mock 
chroot from scratch:
```bash
$ sudo mock --init --no-bootstrap-chroot --config-opts chroot_setup_cmd='install dnf @buildsys-build' -r fedora-36-x86_64
```

By default, it creates a `config.tar.gz` located at `/var/cache/mock/fedora-36-x86_64/root_cache/`.
Second, build the docker image:
```bash
$ docker build -f dockerfiles/fedora.Dockerfile -t qubes-builder-fedora /var/cache/mock/fedora-36-x86_64/root_cache/
```

## Qubes executor

We assume that the [template](https://www.qubes-os.org/doc/templates/) chosen
for building components inside a disposable qube is `fedora-35`. Install the
following dependencies inside the template:

```bash
$ sudo dnf install -y createrepo_c debootstrap devscripts dpkg-dev git mock pbuilder which perl-Digest-MD5 perl-Digest-SHA python3-pyyaml python3-sh rpm-build rpmdevtools wget python3-debian reprepro systemd-udev
```

Then, clone the disposable template based on Fedora 35, `fedora-35-dvm`, to
`qubes-builder-dvm`. Set its private volume storage space to at least 30 GB.
You must install `rpc/qubesbuilder.FileCopyIn` and
`rpc/qubesbuilder.FileCopyOut` in `qubes-builder-dvm` in
`/usr/local/etc/qubes-rpc`.

Let's assume that the qube hosting `qubes-builder` is called `work-qubesos`.
(If you're using a different name, make sure to adjust your policies.) In
`dom0`, copy `rpc/policy/50-qubesbuilder.policy` to `/etc/qubes/policy.d`.

Now, start the disposable template `qubes-builder-dvm` and create the following
directories:

```bash
$ sudo mkdir -p /rw/bind-dirs/builder /rw/config/qubes-bind-dirs.d
```

Create the file `/rw/config/qubes-bind-dirs.d/builder.conf` with the contents:

```
binds+=('/builder')
```

Append to `/rw/config/rc.local` the following:

```
mount /builder -o dev,suid,remount
```

Set `qubes-builder-dvm` as the default disposable template for `work-qubesos`:

```bash
$ qvm-prefs work-qubesos default_dispvm qubes-builder-dvm
```


## Build stages

The build process consists of the following stages:

- fetch
- prep
- build
- post
- verify
- sign
- publish
- upload

Currently, only these are used:

- fetch (download and verify sources)
- prep (create source packages)
- build (build source packages)
- sign (sign built packages)
- publish (publish signed packages)
- upload (upload published repository to a remote server)


## Plugins

- `fetch` --- Manages the general fetching of sources
- `source` --- Manages general distribution sources
- `source_rpm` --- Manages RPM distribution sources
- `source_deb` --- Manages Debian distribution sources
- `build` --- Manages general distribution building
- `build_rpm` --- Manages RPM distribution building
- `build_deb` --- Manages Debian distribution building
- `sign` --- Manages general distribution signing
- `sign_rpm` --- Manages RPM distribution signing
- `sign_deb` --- Manages Debian distribution signing
- `publish` --- Manages general distribution publishing
- `publish_rpm` --- Manages RPM distribution publishing
- `publish_deb` --- Manages Debian distribution publishing
- `upload` --- Manages general distribution uploading
- `template` --- Manages general distribution releases
- `template_rpm` --- Manages RPM distribution releases
- `template_deb` --- Manages Debian distribution releases
- `template_whonix` --- Manages Whonix distribution releases


## CLI

```bash
Usage: qb [OPTIONS] COMMAND [ARGS]...

  Main CLI

Options:
  --verbose / --no-verbose  Increase log verbosity.
  --debug / --no-debug      Print full traceback on exception.
  --builder-conf TEXT       Path to configuration file (default: builder.yml).
  --log-file TEXT           Path to log file to be created.
  -c, --component TEXT      Specify component to treat (can be repeated).
  -d, --distribution TEXT   Set distribution to treat (can be repeated).
  -t, --template TEXT       Set template to treat (can be repeated).
  -o, --option TEXT         Set builder configuration value (can be repeated).
  --help                    Show this message and exit.

Commands:
  package     Package CLI
  template    Template CLI
  repository  Repository CLI
  installer   Installer CLI
  config      Config CLI

Stages:
    fetch prep build post verify sign publish upload

Remark:
    The Qubes OS components are separated into two groups: standard components
    and template components. Standard components will produce distribution
    packages to be installed in TemplateVMs or StandaloneVMs, while template
    components will produce template packages to be installed via qvm-template.
```

You can use the provided development `builder-devel.yml` configuration file
under `example-configs` named `builder.yml` in the root of `qubes-builderv2`
(like the legacy `qubes-builder`).

Artifacts can be found under `artifacts` directory:

```
artifacts/
├── components          <- Stage artifacts for each component version and distribution.
├── distfiles           <- Extra source files.
├── repository          <- Qubes local builder repository (metadata are generated each time inside cages).
├── repository-publish  <- Qubes OS repositories that are uploaded to {yum,deb,...}.qubes-os.org.
├── sources             <- Qubes components source.
└── templates           <- Template artifacts.
```

### Package

You can start building the components defined in this development configuration
with:

```bash
$ ./qb package fetch prep build
```

If GPG is set up on your host, specify the key and client to be used inside
`builder.yml`. Then, you can test the sign and publish stages:

```bash
$ ./qb package sign publish
```

You can trigger the whole build process as follows:

```bash
$ ./qb package all
```

It is possible to initialize a chroot cache, e.g. for Mock and pbuilder, by calling
Package CLI with stage `init-cache`. This particular stage is not included in
the `all` alias. Indeed, if a cache is detected at `prep` ou `build` stages, it
will be used. As cache could be provided either by using `init-cache` or any
other method that a user would use, we keep it as dedicated call.


### Template

Similarly, you can start building the templates defined in this development
configuration with:

```bash
$ ./qb template all
```


### Installer

The build of an ISO is done in several steps. First, it downloads necessary packages
for Anaconda that will be used for Qubes OS installation. Second, it does the same
for Lorax, that is responsible to create the installation runtime. Finally, the step
of creating the ISO is done without network and uses only the downloaded packages.
Download steps are done inside a cage and creating the ISO is done inside a Mock chroot
itself inside a cage. As the ISO creation is done offline, it is important to create
a cache first for Mock. To perform all these simply do:

```bash
$ ./qb installer init-cache all
```

The builder supports only one host distribution at a time. If multiple
is provided in configuration file (e.g. for development purpose), simply call
the builder with the wanted host distribution associated to the ISO.


### Repository

In order to publish to a specific repository, or if you ignored the publish
stage, you can use the `repository` command to create a local repository that
is usable by distributions. For example, to publish only the
`whonix-gateway-16` template:

```bash
./qb -t whonix-gateway-16 repository publish templates-community-testing
```

Or publish all the templates provided in `builder.yml` in
`templates-itl-testing`:

```bash
./qb repository publish templates-itl-testing
```

Similar commands are available for packages, for example:

```bash
./qb -d host-fc32 -c core-qrexec repository publish current-testing
```

and

```bash
./qb repository publish unstable
```

It is not possible to publish packages in template repositories or vice versa.
In particular, you cannot publish packages in the template repositories
`templates-itl`, `templates-itl-testing`, `templates-community`, or
`templates-community-testing`; and you cannot publish templates in the package
repositories `current`, `current-testing`, `security-testing`, or `unstable`. A
built-in filter enforces this behavior.

Normally, everything published in a stable repository, like `current`,
`templates-itl`, or `templates-community`, should first wait in a testing
repository for a minimum of five days. For exceptions in which skipping the
testing period is warranted, you can ignore this rule by using the
`--ignore-min-age` option with the `publish` command.

Please note that the `publish` plugin will not allow publishing to a stable
repository. This is only possible with the `repository` command.


## Signing with Split GPG

If you plan to sign packages with [Split
GPG](https://www.qubes-os.org/doc/split-gpg/), add the following to your
`~/.rpmmacros`:

```
%__gpg /usr/bin/qubes-gpg-client-wrapper

%__gpg_check_password_cmd   %{__gpg} \
        gpg --batch --no-verbose -u "%{_gpg_name}" -s

%__gpg_sign_cmd /bin/sh sh -c '/usr/bin/qubes-gpg-client-wrapper \\\
        --batch --no-verbose \\\
        %{?_gpg_digest_algo:--digest-algo %{_gpg_digest_algo}} \\\
        -u "%{_gpg_name}" -sb %{__plaintext_filename} >%{__signature_filename}'
```


## .qubesbuilder

The `.qubesbuilder` file is a YAML file placed inside a Qubes OS source
component directory, similar to `Makefile.builder` for the legacy Qubes
Builder. It has the following top-level keys:

```
  PACKAGE_SET
  PACKAGE_SET-DISTRIBUTION_NAME (= Qubes OS distribution like `host-fc42` or `vm-trixie`)
  PLUGIN_ENTRY_POINTS (= Keys providing content to be processed by plugins)
```

We provide the following list of available keys:

- `host` --- `host` package set content.
- `vm` --- `vm` package set content.
- `rpm` --- RPM plugins content.
- `deb` --- Debian plugins content.
- `source` --- Fetch and source plugins (`fetch`, `source`, `source_rpm`, and
  `source_deb`) content.
- `build` --- Build plugins content (`build`, `build_rpm`, and `build_deb`).
- `create-archive` --- Create source component directory archive (default:
  `True` unless `files` is provided and not empty).
- `commands` --- Execute commands before plugin or distribution tools
  (`source_deb` only).
- `modules` --- Declare submodules to be included inside source preparation
  (source archives creation and placeholders substitution)
- `files` --- List of external files to be downloaded. It has to be provided
  with the combination of a `url` and a verification method. A verification
  method is either a checksum file or a signature file with public GPG keys.
- `url` --- URL of the external file to download.
- `sha256` --- Path to `sha256` checksum file relative to source directory (in
  combination with `url`).
- `sha512` --- Path to `sha256` checksum file relative to source directory (in
  combination with `url`).
- `signature` --- URL of the signature file of downloaded external file (in
  combination with `url` and `pubkeys`).
- `uncompress` --- Uncompress external file downloaded before verification.
- `pubkeys` --- List of public GPG keys to use for verifying the downloaded
  signature file (in combination with `url` and `signature`).

Here is a non-exhaustive list of distribution-specific keys:
- `host-fc32` --- Fedora 32 for the `host` package set content only
- `vm-bullseye` --- Bullseye for the `vm` package set only

Inside each top level, it defines what plugin entry points like `rpm`, `deb`,
and `source` will take as input. Having both `PACKAGE_SET` and
`PACKAGE_SET-DISTRIBUTION_NAME` with common keys means that it is up to the
plugin to know in which order to use or consider them. It allows for defining
general or distro-specific options.

In a `.qubesbuilder` file, there exist several placeholder values that are
replaced when loading `.qubesbuilder` content. Here is the list of
currently-supported placeholders:

- `@VERSION@` --- Replaced by component version (provided by the `version` file
  inside the component source directory)
- `@REL@` --- Replaced by component release (provided by the `rel` file inside
  the component source directory, if it exists)
- `@BUILDER_DIR@` --- Replaced by `/builder` (inside a cage)
- `@BUILD_DIR@` --- Replaced by `/builder/build`  (inside a cage)
- `@PLUGINS_DIR@` --- Replaced by `/builder/plugins`  (inside a cage)
- `@DISTFILES_DIR@` --- Replaced by `/builder/distfiles`  (inside a cage)
- `@SOURCE_DIR@` --- Replaced by `/builder/<COMPONENT_NAME>` (inside a cage
  where, `<COMPONENT_NAME>` is the component directory name)


### Examples

Here is an example for `qubes-python-qasync`:
```yaml
host:
  rpm:
    build:
    - python-qasync.spec
vm:
  rpm:
    build:
    - python-qasync.spec
vm-buster:
  deb:
    build:
    - debian
vm-bullseye:
  deb:
    build:
    - debian
source:
  files:
  - url: https://files.pythonhosted.org/packages/source/q/qasync/qasync-0.9.4.tar.gz
    sha256: qasync-0.9.4.tar.gz.sha256
```

It defines builds for the `host` and `vm` package sets for all supported RPM
distributions, like Fedora, CentOS Stream, and soon openSUSE with the `rpm`
level key. This key instructs RPM plugins to take as input provided spec files
in the `build` key. For Debian-related distributions, only the `buster` and
`bullseye` distributions have builds defined with the level key `deb`. Similar
to RPM, it instructs Debian plugins to take as input directories provided in
the `build` key.

In the case where `deb` would have been defined also in `vm` like:

```yaml
(...)
vm:
  rpm:
    build:
    - python-qasync.spec
  deb:
    build:
      - debian1
      - debian2
vm-buster:
  deb:
    build:
    - debian
(...)
```

The `vm-buster` content overrides the general content defined by `deb` in `vm`,
so for the `buster` distribution, we would still build only for the `debian`
directory.

In this example, the top level key `source` instructs plugins responsible for
fetching and preparing the component source to consider the key `files`. It is
an array, here only one dict element, for downloading the file at the given
`url` and verifying it against its `sha256` sum. The checksum file is relative
to the component source directory.

If no external source files are needed, like an internal Qubes OS component
`qubes-core-qrexec`,

```yaml
host:
  rpm:
    build:
    - rpm_spec/qubes-qrexec.spec
    - rpm_spec/qubes-qrexec-dom0.spec
vm:
  rpm:
    build:
    - rpm_spec/qubes-qrexec.spec
    - rpm_spec/qubes-qrexec-vm.spec
  deb:
    build:
    - debian
  archlinux:
    build:
    - archlinux
```

we would have no `source` key instructing to perform something else other than
standard source preparation steps and creation (SRPM, dsc file, etc.). In this
case, we have globally-defined builds for RPM, Debian-related distributions,
and ArchLinux (`archlinux` key providing directories as input similar to
Debian).

Some components need more source preparation and processes like
`qubes-linux-kernel`:

```yaml
host:
  rpm:
    build:
    - kernel.spec
source:
  modules:
  - linux-utils
  - dummy-psu
  - dummy-backlight
  files:
  - url: https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-@VERSION@.tar.xz
    signature: https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-@VERSION@.tar.sign
    uncompress: true
    pubkeys:
    - kernel.org-2-key.asc
    - kernel.org-1-key.asc
  - url: https://github.com/PatrickVerner/macbook12-spi-driver/archive/2905d318d1a3ee1a227052490bf20eddef2592f9.tar.gz#/macbook12-spi-driver-2905d318d1a3ee1a227052490bf20eddef2592f9.tar.gz
    uncompress: true
    sha256: macbook12-spi-driver-2905d318d1a3ee1a227052490bf20eddef2592f9.tar.sha256
```

First, the `source` key provides `modules` that instructs the `fetch` and
`source` plugins that there exist `git` submodules that are needed for builds.
In the case of RPM, the spec file has different `Source` macros depending on
archives with submodule content. The source preparation will create an archive
for each submodule and render the spec file according to the submodule archive
names. More precisely, for `qubes-linux-kernel` commit hash
`b4fdd8cebf77c7d0ecee8c93bfd980a019d81e39`, it will replace placeholders inside
the spec file `@linux-utils@`, `@dummy-psu@`, and `@dummy-backlight@` with
`linux-utils-97271ba.tar.gz`, `dummy-psu-97271ba.tar.gz`, and
`dummy-backlight-3342093.tar.gz`  respectively, where `97271ba`, `97271ba`, and
`3342093` are short commit hash IDs of submodules.

Second, in the `files` key, there is another case where an external file is
needed but the component source directory holds only public keys associated
with archive signatures and not checksums. In that case, `url` and `signature`
are files to be downloaded and `pubkeys` are public keys to be used for source
file verification. Moreover, sometimes the signature file contains the
signature of an uncompressed file. The `uncompress` key instructs `fetch`
plugins to uncompress the archive before proceeding to verification.

**Reminder:** These operations are performed inside several cages. For example,
the download is done in one cage, and the verification is done in another cage.
This allows for separating processes that may interfere with each other,
whether intentionally or not.

For an internal Qubes OS component like `qubes-core-qrexec`, the `source`
plugin handles creating a source archive that will be put side to the packaging
files (spec file, Debian directory, etc.) to build packages. For an external
Qubes OS component like `qubes-python-qasync` (same for `xen`, `linux`,
`grub2`, etc.), it uses the external file downloaded (and verified) side to the
packaging files to build packages. Indeed, the original source component is
provided by the archive downloaded and only packaging files are inside the
Qubes source directory. Packaging includes additional content like patches,
configuration files, etc. In very rare cases, the packaging needs both a source
archive of the Qubes OS component directory and external files. This is the
case `qubes-vmm-xen-stubdom-linux`:

```yaml
host:
  rpm:
    build:
    - rpm_spec/xen-hvm-stubdom-linux.spec
source:
  create-archive: true
  files:
  - url: https://download.qemu.org/qemu-6.1.0.tar.xz
    signature: https://download.qemu.org/qemu-6.1.0.tar.xz.sig
    pubkeys:
    - keys/qemu/mdroth.asc
    - keys/qemu/pbonzini.asc
  - url: https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.10.105.tar.xz
    signature: https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.10.105.tar.sign
    uncompress: true
    pubkeys:
    - keys/linux/greg.asc
  - url: https://busybox.net/downloads/busybox-1.31.1.tar.bz2
    signature: https://busybox.net/downloads/busybox-1.31.1.tar.bz2.sig
    pubkeys:
    - keys/busybox/vda_pubkey.asc
  - url: https://freedesktop.org/software/pulseaudio/releases/pulseaudio-14.2.tar.xz
    sha512: checksums/pulseaudio-14.2.tar.xz.sha512
  - url: https://github.com/libusb/libusb/releases/download/v1.0.23/libusb-1.0.23.tar.bz2
    sha512: checksums/libusb-1.0.23.tar.bz2.sha512
```

By default, if files are provided, plugins treat components as external Qubes
OS components, which means that archiving the component source directory is not
performed, because it's useless to package the packaging itself. For this
particular component in Qubes OS, there are several directories needed from
source component directories. Consequently, the packaging has been made in such
a way so as to extract from the source archive only these needed directories.
In order to force archive creation, (or disable it), the `create-archive`
boolean can be set in the `source` keys at the desired value, here `true`.

For Debian distributions, it is sometimes necessary to execute a custom command
before source preparation. This is the case, for example, for `i3`:

```yaml
host:
  rpm:
    build:
    - i3.spec
vm:
  rpm:
    build:
    - i3.spec
  deb:
    build:
    - debian-pkg/debian
    source:
      commands:
      - '@PLUGINS_DIR@/source_deb/scripts/debian-quilt @SOURCE_DIR@/series-debian.conf @BUILD_DIR@/debian/patches'
source:
  files:
  - url: https://i3wm.org/downloads/i3-4.18.2.tar.bz2
    sha512: i3-4.18.2.tar.bz2.sha512
```

Inside the `deb` key, there is a command inside the `commands` array to execute
the `debian-quilt` script provided by the `source_deb` plugin with a series of
patch files located in the source directory (path inside a cage) to the
prepared source directory, here the build directory (path inside a cage).

**Note:** All commands provided are executed before any plugin tools or
distribution tools like `dpkg-*`. This is only available for Debian
distributions and not RPM distributions, as similar processing is currently not
needed.

## Qubes builder configuration

Options available in `builder.yml`:

- `git`:
  - `baseurl: str` --- Base url of git repos (default: https://github.com).
  - `prefix: str` --- Which repository to clone (default: QubesOS/qubes-).
  - `suffix: str` --- git suffix (default: .git).
  - `branch: str` --- git branch (default: master).
  - `maintainers: List[str]` --- List of extra fingerprint allowed for signature verification of git commit and tag.

- `artifacts-dir: str` --- Path to artifacts directory.

- `plugins-dirs: List[str]` --- List of path to plugin directory. By default, the local plugins directory is prepended to the list.

- `backend-vmm: str` --- Backend Virtual Machine (default and only supported value: xen).

- `debug: bool` --- Print full traceback on exception (default: False).

- `verbose: bool` --- Increase log verbosity (default: False).

- `qubes-release: str` --- Qubes OS release e.g. r4.2.

- `min-age-days: int` --- Minimum days for testing component or template allowed to reach stable repositories (default: 5).

- `gpg-client: str`: GPG client to use, either `gpg` or `qubes-gpg-client-wrapper`.

- `iso: Dict`:
  - `kickstart: str` --- Image installer kickstart.
  - `iso-flavor: str` --- Image name will be named as `Qubes-<iso-version>-<iso-flavor>-<arch>.iso`.
  - `use-kernel-latest: bool` --- If True, use `kernel-latest` when building installer runtime and superseed `kernel` in the installation. It allows to boot installer and QubesOS with the latest drivers provided by stable kernels and not only long term supported ones by default.

- `use-qubes-repo: Dict`:
  `version: str` --- Use Qubes packages repository to satisfy build dependents. Set to target version of Qubes you are building packages for (like "4.1", "4.2" etc.).
  `testing: bool` --- When used with `use-qubes-repo:version`, enable testing repository for that version (in addition to stable).

- `sign-key: Dict` --- Fingerprint for signing content.
  - `rpm: str` --- RPM content.
  - `deb: str` --- Debian content.
  - `iso: str` --- ISO content.

- `less-secure-signed-commits-sufficient: list` --- List of component names where signed commits is allowed instead of requiring signed tags. This is less secure because only commits that have been reviewed are tagged.

- `timeout: int`: Abort build after given timeout, in seconds.

- `repository-publish: Dict` ---  Testing repository to use at publish stage.
  - `components: str` --- Components . This is either `current-testing`, `security-testing` or `unstable`.
  - `templates: str` --- Testing repository for templates at publish stage. This is either `templates-itl-testing` or `templates-community-testing`.

- `distributions: List[str]` --- Distribution for packages provided as <package-set>-<distribution>.<architecture>. Default architecture is `x86_64` and can be ommited. Some examples: host-fc32, host-fc42.ppc64 or vm-trixie.

- `components: List[Union[str, Dict]]` -- List of components you want to build. See example configs for sensible lists. The order of components is important - it should reflect build dependencies, otherwise build would fail.
  - `<component_name>` --- Component name provided as string
  - `<component_name>`: --- Component name provided as dict to pass or override values
    - `branch: str` --- override default git branch.
    - `url: str` --- provide the full url of the component.
    - `maintainers: List[str]` --- List of extra fingerprint allowed for signature verification of git commit and tag.
    - `timeout: int` --- Abort build after given timeout, in seconds.

- `templates: List[Dict]` -- List of templates you want to build. See example configs for sensible lists.
  - `<template_name>`: --- Template name
    - `dist: str` --- Underlying distribution, e.g. fc42, bullseye, etc.
    - `flavor: str` --- If applies, specify template flavor, e.g. minimal, xfce, whonix-gateway, whonix-workstation, etc.
    - `options: List[str]` --- Provides template build options, e.g. minimal, no-recommends, firmware, etc.

- `repository-upload-remote-host: Dict` --- Rsync URL for uploading local repository content
  - `rpm: str` --- RPM content
  - `deb: str` --- Debian content
  - `iso: str` --- ISO content

- `executor: Dict` --- Specify default executor to use
  - `type: str` --- Executor type: qubes, docker, podman or local.
  - `options: Dict`:
    - `image: str` --- Container image to use. Specific to docker or podman type.
    - `dispvm: str` --- Disposable template VM to use (NOT IMPLEMENTED YET. HARDCODED TO 'qubes-builder-dvm').
    - `directory: str` --- Base directory for local executor to create temporary directories.
    - `clean: bool` --- Do not clean container, disposible qube or temporary local folder.

- `stages: List[str, Dict]` --- List of stages to trigger.
  - `<stage_name>: str` --- Stage name
  - `<stage_name>: Dict` --- Stage name provided as dict to override executor to use.
    - `executor: Dict` --- Specify executor to use for this stage
