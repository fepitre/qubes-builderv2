FROM debian:stable
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Install dependencies for Qubes Builder
RUN apt-get update && \
    apt-get install -y debootstrap devscripts dpkg-dev git wget python3-debian\
    && apt-get clean all

RUN mkdir /builder /builder/plugins /builder/build
