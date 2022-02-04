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

For now, only Docker or Podman executor is available and Qubes OS DispVM is coming really soon. Only Docker executor
inside a Fedora AppVM has been used by the author for validating the current development.

## How-to

### Dependencies

- createrepo_c 
- devscripts
- gpg
- qubes-gpg-split
- python3-pyyaml
- rpmdevtools
- docker
- python3-docker

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
