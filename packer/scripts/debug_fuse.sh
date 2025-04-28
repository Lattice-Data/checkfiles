#!/bin/bash
# FUSE debug script for Checkfiles AMI
# This script gathers detailed information about FUSE installation and status

set -e

echo "=== FUSE Debug Information ==="
echo ""

echo "=== System Information ==="
uname -a
cat /etc/os-release
echo ""

echo "=== Available FUSE Packages ==="
apt-cache search fuse | grep -i fuse
echo ""

echo "=== Installed FUSE Packages ==="
dpkg -l | grep -i fuse || echo "No packages found"
echo ""

echo "=== FUSE Kernel Module ==="
lsmod | grep fuse || echo "No fuse module loaded"
echo ""

echo "=== FUSE Device ==="
ls -la /dev/fuse || echo "No /dev/fuse device found"
echo ""

echo "=== FUSE Binary ==="
which fusermount || echo "fusermount not found"
ls -la /bin/fusermount* /usr/bin/fusermount* 2>/dev/null || echo "No fusermount binaries found"
echo ""

echo "=== FUSE Configuration ==="
cat /etc/fuse.conf 2>/dev/null || echo "No fuse.conf found"
echo ""

echo "=== Kernel Capabilities ==="
cat /proc/filesystems | grep fuse || echo "fuse filesystem not supported by kernel"
echo ""

echo "=== Mounted Filesystems ==="
mount | grep fuse || echo "No fuse filesystems mounted"
echo ""

echo "=== Goofys Executable ==="
which goofys || echo "goofys not found"
echo ""

echo "=== Testing FUSE Mount ==="
mkdir -p /tmp/fuse_test 2>/dev/null || true
fusermount -V || echo "fusermount command failed"
echo ""

echo "=== FUSE Debug Information Complete ===" 