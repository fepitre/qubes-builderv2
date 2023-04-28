FROM ubuntu@sha256:67211c14fa74f070d27cc59d69a7fa9aeff8e28ea118ef3babc295a0428a6d21
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Install dependencies for Qubes Builder
RUN apt-get update && \
    apt-get install -y sudo curl debootstrap devscripts dpkg-dev git wget python3-debian e2fsprogs pbuilder tree \
        reprepro psutils fdisk udev rpm \
    && apt-get clean all

# Create build user
RUN useradd -m user -u 1000
RUN usermod -aG sudo user && echo '%sudo ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/sudo

# Create needed folders
RUN mkdir /builder /builder/plugins /builder/build /builder/distfiles /builder/cache /builder/repository /builder/sources
RUN chown -R user /builder

USER user
