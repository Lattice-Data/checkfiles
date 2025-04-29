#!/bin/bash
# FUSE debug script for Checkfiles AMI
# This script ONLY gathers diagnostic information about FUSE installation and status
# It does NOT configure FUSE (configuration is handled by install_goofys_and_validatefiles.sh)

set -e

echo "=== FUSE Diagnostic Information ==="
echo "This script is read-only and does not modify any configuration"
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
ls -la $(which goofys 2>/dev/null) || echo "Cannot access goofys executable"
echo ""

echo "=== ValidateFiles Executable ==="
which validatefiles || echo "validatefiles not found" 
which validateFiles || echo "validateFiles (capitalized) not found"
echo ""

echo "=== FUSE Diagnostic Information Complete ===" 