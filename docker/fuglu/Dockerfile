FROM debian:stable-slim as python3-base
ENV PYTHONPATH=/fuglu
WORKDIR /fuglu
RUN mkdir -p /var/log/fuglu && \
  chown nobody:nogroup /var/log/fuglu && \
  chmod 777 /var/log/fuglu
RUN echo "deb http://deb.debian.org/debian stable main non-free" > /etc/apt/sources.list && \
  echo "deb http://security.debian.org/debian-security stable/updates main non-free" >> /etc/apt/sources.list && \
  echo "deb http://deb.debian.org/debian stable-updates main non-free" >> /etc/apt/sources.list
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-pip clamav-base unrar
RUN pip3 install --upgrade pip setuptools wheel

FROM python3-base as builder
RUN DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y make gcc libffi-dev python3-dev
COPY requirements.txt /
RUN pip3 install -r /requirements.txt
CMD /fuglu/startscript/fuglu --foreground