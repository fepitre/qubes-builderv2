FROM scratch
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

# Use Mock chroot
ADD cache.tar.gz /

COPY configure-rpm.sh /tmp
RUN /tmp/configure-rpm.sh && rm -f /tmp/configure-rpm.sh

COPY setup-devtools.sh /tmp
RUN /tmp/setup-devtools.sh && rm -f /tmp/setup-devtools.sh

USER user
