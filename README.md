Qubes OS Builder
===

This is the next generation of Qubes OS builder.

The new Qubes OS builder leverage container or DispVM isolation to perform every stage of a build and release process. 
From fetching sources and actually building them, everything will be executed inside a `cage` (either DispVM or container) with
the help of what we call an `executor`. For every single command that needs to perform an action on sources for example, 
like cloning and verifying Git sources, rendering a SPEC file, generating SRPM or Debian source packages, etc.,
a fresh and new cage will be used. It remains only the signing, publishing and uploading processes being executed locally and not
inside a cage. This is to be improved in the future. For now, only Docker, Podman, Local and Qubes executors are available.

> **Remark**: Only Docker, Local (`sign`, `publish` and `upload` stages only) and Qubes executors inside a Fedora AppVM have been used by the author for validating the current development.

## Work in progress

We provide brief instructions in order to help people who want to start contributing to this work in progress.

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
- upload

Currently, only those are used:

- fetch (downloading and verify sources)
- prep (creating source packages)
- build (building source packages)
- sign (signing built packages)
- publish (publishing signed packages)
- upload (upload publish repository to a remote mirror)

### Plugins

- `fetch` - Manages generic fetch source,
- `source` - Manages generic distribution source,
- `source_rpm` - Manages RPM distribution source,
- `source_deb` - Manages Debian distribution source,
- `build` - Manages generic distribution build,
- `build_rpm` - Manages RPM distribution build,
- `build_deb` - Manages Debian distribution build,
- `sign` - Manages generic distribution sign,
- `sign_rpm` - Manages RPM distribution sign,
- `sign_deb` - Manages Debian distribution sign,
- `publish` - Manages generic distribution publication,
- `publish_rpm` - Manages RPM distribution publication,
- `publish_deb` - Manages Debian distribution publication,
- `upload` - Manages generic distribution upload,
- `template` - Manages generic distribution release,
- `template_rpm` - Manages RPM distribution release,
- `template_deb` - Manages Debian distribution release,
- `template_whonix` - Manages Whonix distribution release.

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
├── repository-publish  <- Qubes OS repositories that are uploaded to {yum,deb,...}.qubes-os.org.
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

The `.qubesbuilder` file is a YAML format file placed inside a Qubes OS source component directory, similar to what is
`Makefile.builder` for the legacy Qubes Builder. It has top level keys:

```
  PACKAGE_SET
  PACKAGE_SET-DISTRIBUTION_NAME (= Qubes OS distribution like `host-fc42` or `vm-trixie`.)
  PLUGIN_ENTRY_POINTS (= Keys providing content to be processed by plugins)
```

We provide the list of available keys where examples are given in the next sections:

- `host` - `host` package set content.
- `vm` - `vm` package set content.
- `rpm` - RPM plugins content.
- `deb` - Debian plugins content.
- `source` - Fetch and source plugins (`fetch`, `source`, `source_rpm` and `source_deb`) content.
- `build` - Build plugins content (`build`, `build_rpm` and `build_deb`).
- `create-archive` - Create source component directory archive (default: `True` unless `files` is provided and not empty).
- `commands` - Execute commands before plugin or distribution tools (`source_deb` only).
- `modules` - Declare submodules to be included inside source preparation (source archives creation and placeholders substitution)
- `files` - List of external files to be downloaded. It has to be provided with combination of `url` and a verification method.
            A verification method is either provided by a checksum file or a signature file with public GPG keys.
- `url`   - URL of the external file to download.
- `sha256` - Path to `sha256` checksum file relative to source directory (in combination of `url`).
- `sha512` - Path to `sha256` checksum file relative to source directory (in combination of `url`).
- `signature` - URL of the signature file of downloaded external file (in combination of `url` and `pubkeys`).
- `uncompress` - Uncompress external file downloaded before verification.
- `pubkeys` - List of public GPG keys to use for verifying the downloaded signature file (in combination of `url` and `signature`).

with non-exhaustive distribution specific keys like:
- `host-fc32` - Fedora 32 for `host` package set content only,
- `vm-bullseye` - Bullseye for `vm` package set only.

Inside each top level, it defines what plugin entry points like `rpm`, `deb` or `source` will take as input. Having both
PACKAGE_SET and PACKAGE_SET-DISTRIBUTION_NAME with common keys is up to the plugin to know in which order to use or
consider them. It allows defining general or per distro options.

In a `.qubesbuilder` file, there exist several placeholder values that are replaced when loading `.qubesbuilder` content.
Here is the list of currently supported placeholders by plugins:

- `@VERSION@` - Replaced by component version (provided by `version` file inside component source directory),
- `@REL@` - Replaced by component release (provided by `rel` file inside component source directory if exists),
- `@BUILDER_DIR@` - Replaced by `/builder` (inside a cage),
- `@BUILD_DIR@` - Replaced by `/builder/build`  (inside a cage),
- `@PLUGINS_DIR@` - Replaced by `/builder/plugins`  (inside a cage),
- `@DISTFILES_DIR@` - Replaced by `/builder/distfiles`  (inside a cage),
- `@SOURCE_DIR@` - Replaced by `/builder/<COMPONENT_NAME>` (inside a cage where COMPONENT_NAME is the component directory name).

#### Examples

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

It defines builds for `host` and `vm` package sets for all supported RPM distributions like Fedora, CentOS Stream
and soon openSUSE with `rpm` level key. This key instructs RPM plugins to take as input provided spec files in
`build` key. For Debian related distributions, only `buster` and `bullseye` distributions have build defined with
the level key `deb`. Similar to RPM, it instructs Debian plugins to take as input, provided directories in `build` key.

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
`vm-buster` content override general content defined by `deb` in `vm` so for `buster` distribution, we would
have still build only for `debian` directory.

In this example, the top level key `source` instructs plugins responsible to fetch and prepare component source
to consider the key `files`. It is an array, here only one dict element, for downloading the file at the given `url`
and verify it against its `sha256` sum. The checksum file is relative to component source directory.

If no external source files is needed, like an internal Qubes OS component `qubes-core-qrexec`,
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

we would have no `source` key instructing to perform something else than standard source preparation steps and creation 
(SRPM, dsc file, etc.). In this case, we have global defined builds for RPM, Debian related distributions and ArchLinux
(`archlinux` key providing directories as input similar to Debian).

Some components need more source preparation and processes like `qubes-linux-kernel`:
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

First, `source` key provides `modules` that instructs `fetch` and `source` plugins that there exists `git`
submodules that are needed for builds. In the case of RPM, the spec file has different `Source` macros depending on
archives with submodules content. The source preparation will create an archive for each submodule and 
render the spec file accordingly to the submodule archive names. More precisely, for `qubes-linux-kernel` commit hash 
`b4fdd8cebf77c7d0ecee8c93bfd980a019d81e39`, it will replace placeholders inside the spec file 
@linux-utils@, @dummy-psu@ and @dummy-backlight@ respectively by `linux-utils-97271ba.tar.gz`, `dummy-psu-97271ba.tar.gz`
and `dummy-backlight-3342093.tar.gz` where `97271ba`, `97271ba` and `3342093` are short commit hash IDs of submodules.

Second, in `files` key, there is another case where an external file is needed but the component source dir holds only
public keys associated to archive signatures and not checksums. In that case, `url` and `signature` are files to be
downloaded and `pubkeys` are public keys to be used for source files verification. Moreover, sometimes signature file
is against uncompressed file. `uncompress` key instructs `fetch` plugins to uncompress the archive before proceeding to
the verification.

> Note: We remind that all these operations are performed inside several cages. For example, download is done in one
> cage and verify is done in another cage. It allows to separate processes that may interfere intentionally or not
> between them.

For an internal Qubes OS component like `qubes-core-qrexec`, the `source` plugin handles to create a source archive
that will be put side to the packaging files (spec file, Debian directory, etc.) to build packages. For an external
Qubes OS component like `qubes-python-qasync` (same for `xen`, `linux`, `grub2`, etc.) it uses the external file 
downloaded (and verified) side to the packaging files to build packages. Indeed, the original source component is 
provided by the archive downloaded and only packaging files are inside Qubes source directory. Packaging includes 
additional content like patches, configuration files, etc. In very rare cases, the packaging needs both a source 
archive of the Qubes OS component directory and external files. This is the case `qubes-vmm-xen-stubdom-linux`:

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

By default, if files are provided, plugins treat component as external Qubes OS component which means that archive for
component source directory is not performed because it's useless to package the packaging itself. For this particular
component in Qubes OS, there is several directories needed from source component directories. In consequence, packaging
has been made in order to extract from source archive only these needed directories. In order to force archive creation,
(or disable it), `create-archive` is a boolean to be set in `source` keys at the wanted value, here `true`.

For Debian distributions, it is needed sometimes to execute a custom command before source preparation. This is
the case for example for `i3`:

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

Inside `deb` key, it is provided a command inside `commands` array to execute `debian-quilt` script provided by the
`source_deb` plugin with a series of patches file located in source directory (path inside a cage) to the prepared source
directory, here build directory (path inside a cage).

> Note: All commands provided are executed before any plugins tools or distribution tools like `dpkg-*`. This is only
> available for Debian distributions and not RPM distributions as similar processing is currently not needed.
