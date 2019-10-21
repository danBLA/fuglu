FROM centos:centos7 as fuglu-testenv-py3

ENV PYTHONPATH=/fuglu
WORKDIR /fuglu

# ssdeep -> see http://python-ssdeep.readthedocs.io/en/latest/installation.html#install-on-centos-7
#        => NOTE: not all versions working...
RUN yum  -y groupinstall "Development Tools"
RUN yum  -y install epel-release
RUN yum  -y install unar python36 python36-nose python36-pip libffi-devel ssdeep-devel ssdeep-libs python36-devel wget libxml2

#unfortunately, unrar is no longer available in EPEL https://github.com/fumail/fuglu/issues/87
#RUN yum -y install ftp://ftp.pbone.net/mirror/ftp5.gwdg.de/pub/opensuse/repositories/home:/Kenzy:/modified:/C7/CentOS_7/x86_64/unrar-5.0.12-2.1.x86_64.rpm
RUN wget https://www.rarlab.com/rar/rarlinux-x64-5.6.0.tar.gz; tar -zxf rarlinux-x64-5.6.0.tar.gz; cd rar; cp -v rar unrar /usr/local/bin/; cd -
RUN yum update -y
RUN pip3 install --upgrade pip setuptools wheel
RUN pip3 install rarfile rednose sqlalchemy python-magic pyspf py3dns mock ssdeep redis geoip2 beautifulsoup4 lxml pysrs pylzma
# Install current domainmagic version for python 2/3
RUN wget https://gitlab.com/fumail/domainmagic/-/archive/master/domainmagic-master.zip; unzip -e domainmagic-master.zip; cd domainmagic-master/; python setup.py install --force; python3 setup.py install --force; cd -; rm -rf domainmagic-master domainmagic-master.zip

# with source
from fuglu-testenv-py3 as fuglu-py3-source
COPY ./fuglu/src/. /fuglu

# with config
from fuglu-py3-source as fuglu-py3-configured
COPY docker/fuglu-testenv-contained/conf/. /etc/fuglu/

CMD python3 /fuglu/startscript/fuglu --foreground --lint && python3 /fuglu/startscript/fuglu --foreground
