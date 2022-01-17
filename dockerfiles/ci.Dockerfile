FROM localhost/qubes-builder-fedora:latest
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

RUN dnf -y update && \
    dnf install -y python3-requests-mock python3-pytest python3-pytest-mock python3-pytest-cov \
        python3-podman python3-yaml python3-docker podman docker && \
    dnf clean all

RUN mkdir /qubesbuilder
WORKDIR /qubesbuilder
