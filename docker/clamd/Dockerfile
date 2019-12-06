FROM debian:stable-slim as release

RUN apt-get update
RUN apt-get -y install clamav-daemon
# See https://github.com/moby/moby/issues/31243#issuecomment-406879017 for more informations
RUN usermod -a -G tty clamav
RUN /bin/mkdir /run/clamav && \
  /bin/chown clamav /run/clamav
COPY docker/clamd/clamd.conf /etc/clamav/clamd.conf
RUN /usr/bin/freshclam
CMD clamd
