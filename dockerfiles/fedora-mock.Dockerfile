FROM scratch
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Use Mock chroot
ADD cache.tar.gz /

# Install dependencies for Qubes Builder
RUN dnf -y update && \
    dnf install -y dnf-plugins-core createrepo_c debootstrap devscripts dpkg-dev git mock pbuilder \
        which perl-Digest-MD5 perl-Digest-SHA python3-pyyaml e2fsprogs \
        python3-sh rpm-build rpmdevtools wget python3-debian reprepro systemd-udev \
        tree python3-jinja2-cli pacman m4 asciidoc rsync psmisc zstd archlinux-keyring debian-keyring arch-install-scripts \
    && dnf clean all

# Install devtools for Archlinux
RUN git clone -n https://gitlab.archlinux.org/fepitre/devtools && \
	cd devtools && \
	git checkout 69ecbff0d3425efcdb27a4789f184d4108c1a5c3 && \
	make install DESTDIR=/ PREFIX=/usr/local && \
	ln -s /usr/local/bin/archbuild /usr/local/bin/qubes-x86_64-build

# Create build user
RUN useradd -m user
RUN usermod -aG wheel user && echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/wheel

# Create needed folders
RUN mkdir /builder /builder/plugins /builder/build /builder/distfiles /builder/cache /builder/repository /builder/sources
RUN chown -R user /builder

USER user
