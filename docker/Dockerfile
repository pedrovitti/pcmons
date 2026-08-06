#Runtime for exercising pcmons without a real private cloud.
#
#Python 2.7 is what the code targets, so the image pins it. Debian buster has
#moved to archive.debian.org, hence the rewritten sources.list.
FROM python:2.7-slim

RUN printf 'deb http://archive.debian.org/debian buster main\n\
deb http://archive.debian.org/debian-security buster/updates main\n' > /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update -qq \
    && apt-get install -y --no-install-recommends \
        procps \
        net-tools \
        default-mysql-client \
        gcc \
        libc6-dev \
        default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

#The probes read absolute paths (/var/log/auth.log, /etc/crypttab, ...) that a
#container does not have. Install fixture copies at exactly those paths so the
#shipped code runs unmodified.
COPY docker/fixtures/ /

#virsh needs a real libvirt host; the stub replays recorded output instead.
COPY docker/bin/virsh /usr/local/bin/virsh
RUN chmod +x /usr/local/bin/virsh

WORKDIR /opt/pcmons
ENV PYTHONPATH=/opt/pcmons
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "docker/smoke_test.py"]
