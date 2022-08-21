FROM debian@sha256:b9b1f4a7df16fcf7f287802d827b80f481a1e4caecb62c40c2e26fdebdc2eab9
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Install dependencies for Qubes Builder
RUN apt-get update && \
    apt-get install -y sudo curl debootstrap devscripts dpkg-dev git wget python3-debian e2fsprogs pbuilder tree \
    && apt-get clean all

# Create build user
RUN useradd -m user -u 1000
RUN usermod -aG sudo user && echo '%sudo ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/sudo

# Create needed folders
RUN mkdir /builder /builder/plugins /builder/build /builder/distfiles /builder/cache /builder/repository
RUN chown -R user /builder

USER user
