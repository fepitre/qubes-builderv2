FROM debian@sha256:2ee2a0213896cb43334a2441782368dcf61f15bc6515d332ea4d345e63415c71
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Install dependencies for Qubes Builder
RUN apt-get update && \
    apt-get install -y sudo curl debootstrap devscripts dpkg-dev git wget python3-debian e2fsprogs pbuilder tree \
        reprepro psutils fdisk udev rpm python3-yaml \
    && apt-get clean all

# Create build user
RUN useradd -m user -u 1000
RUN usermod -aG sudo user && echo '%sudo ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/sudo

# Create needed folders
RUN mkdir /builder /builder/plugins /builder/build /builder/distfiles /builder/cache /builder/repository /builder/sources
RUN chown -R user /builder

USER user
