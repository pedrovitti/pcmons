#!/bin/sh
#Packs the VM agent into monitoring.tar, the bundle Startup.sh copies to
#/root/monitoring.tar and untars into /opt/monitoring on a booting VM.
#Run it from anywhere; the archive is written next to this script.
set -e

cd "$(dirname "$0")"

#keep macOS tar from adding AppleDouble ._ entries to the archive
COPYFILE_DISABLE=1
export COPYFILE_DISABLE

tar -cf monitoring.tar \
    Monitor.py \
    MemoryMonitor.py \
    SystemLoadMonitor.py \
    HTTPConMonitor.py \
    SSHAccessMonitor.py \
    AvailabilityMonitor.py \
    BackupMonitor.py \
    EncryptionMonitor.py \
    IntegrityMonitor.py \
    MalwareMonitor.py \
    PasswordMonitor.py \
    VulnerabilityMonitor.py \
    settings.py

echo "monitoring.tar rebuilt from the current sources"
