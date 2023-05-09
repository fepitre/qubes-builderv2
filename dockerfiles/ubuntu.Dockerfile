FROM ubuntu@sha256:67211c14fa74f070d27cc59d69a7fa9aeff8e28ea118ef3babc295a0428a6d21
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

COPY configure-deb.sh /tmp
RUN /tmp/configure-deb.sh && rm -f /tmp/configure-deb.sh

USER user
