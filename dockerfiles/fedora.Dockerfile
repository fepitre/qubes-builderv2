FROM fedora@sha256:a1aff3e01bb667ededb2e4d895a1f1f88b7d329bd22402d4a5ba5e7f1c7a48cb
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

COPY configure-rpm.sh /tmp
RUN /tmp/configure-rpm.sh && rm -f /tmp/configure-rpm.sh

COPY setup-devtools.sh /tmp
RUN /tmp/setup-devtools.sh && rm -f /tmp/setup-devtools.sh

USER user
