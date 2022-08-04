FROM fedora@sha256:cbf627299e327f564233aac6b97030f9023ca41d3453c497be2f5e8f7762d185
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Install dependencies for Qubes Builder
RUN dnf -y update && \
    dnf install -y createrepo_c debootstrap devscripts dpkg-dev git mock pbuilder \
        which perl-Digest-MD5 perl-Digest-SHA python3-pyyaml e2fsprogs \
        python3-sh rpm-build rpmdevtools wget python3-debian reprepro systemd-udev \
    && dnf clean all

RUN mkdir /builder /builder/plugins /builder/build /builder/distfiles

RUN useradd -m user -u 1000

RUN chown -R user /builder

RUN usermod -aG wheel user && echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/wheel

USER user
