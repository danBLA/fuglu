FROM debian:stable-slim as release

RUN apt-get update
RUN apt-get -y install spamassassin

CMD spamd --nouser-config \
  --syslog stderr \
  --helper-home-dir /var/lib/spamassassin \
  --ip-address \
  --allowed-ips 0.0.0.0/0