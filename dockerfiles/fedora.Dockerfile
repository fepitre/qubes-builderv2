FROM fedora:latest
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Install dependencies for Qubes Builder
RUN dnf -y update && \
    dnf install -y createrepo_c debootstrap devscripts dpkg-dev git mock pbuilder \
        which perl-Digest-MD5 perl-Digest-SHA python3-pyyaml e2fsprogs \
        python3-sh rpm-build rpmdevtools wget python3-debian reprepro systemd-udev \
    && dnf clean all

RUN mkdir /builder /builder/plugins /builder/build

RUN useradd -m user -u 1000
