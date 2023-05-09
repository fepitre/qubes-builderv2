FROM debian@sha256:2ee2a0213896cb43334a2441782368dcf61f15bc6515d332ea4d345e63415c71
MAINTAINER Frédéric Pierret <frederic@invisiblethingslab.com>

COPY configure-deb.sh /tmp
RUN /tmp/configure-deb.sh && rm -f /tmp/configure-deb.sh

USER user
