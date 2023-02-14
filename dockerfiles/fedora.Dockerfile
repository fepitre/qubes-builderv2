FROM fedora@sha256:2c5b21348e9b2a0b4c49bd5013be6d406be8594831aba21043393fcfba7252e0
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Install dependencies for Qubes Builder
RUN dnf -y update && \
    dnf install -y createrepo_c debootstrap devscripts dpkg-dev git mock pbuilder \
        which perl-Digest-MD5 perl-Digest-SHA python3-pyyaml e2fsprogs \
        python3-sh rpm-build rpmdevtools wget python3-debian reprepro systemd-udev \
        tree pacman m4 asciidoc rsync \
    && dnf clean all

RUN git clone https://gitlab.archlinux.org/fepitre/devtools && \
	cd devtools && \
	git checkout -b bash-52 d01aca696c250944f96a52f70094e42589190b61 && \
	make install DESTDIR=/ PREFIX=/usr

# Create build user
RUN useradd -m user
RUN usermod -aG wheel user && echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/wheel

# Create needed folders
RUN mkdir /builder /builder/plugins /builder/build /builder/distfiles /builder/cache /builder/repository /builder/sources
RUN mkdir -p /builder/cache/mock
RUN chown -R user /builder

USER user
