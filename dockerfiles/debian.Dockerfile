FROM debian:stable
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Install dependencies for Qubes Builder
RUN apt-get update && \
    apt-get install -y debootstrap devscripts dpkg-dev git wget python3-debian e2fsprogs \
    && apt-get clean all

RUN mkdir /builder /builder/plugins /builder/build

RUN useradd -m user -u 1000
