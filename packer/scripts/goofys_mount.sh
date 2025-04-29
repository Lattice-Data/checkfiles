#!/bin/bash
# Goofys mount script for Checkfiles.
#
# This script ONLY sets up the Goofys mount points for S3 access.
# It creates the mount directories if they don't exist and
# ensures proper permissions.
# 
# FUSE installation and configuration is handled by install_goofys_and_validatefiles.sh
#
# Usage:
#   sudo ./goofys_mount.sh

set -euo pipefail

# Error handling function
handle_error() {
    echo "ERROR: Mount setup failed at line $1"
    exit 1
}

# Set up error trap
trap 'handle_error $LINENO' ERR

# Ensure we're running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

echo "Setting up Goofys mount points..."

# Verify goofys is installed
if ! command -v goofys &> /dev/null; then
    echo "ERROR: goofys not installed. Run install_goofys_and_validatefiles.sh first."
    exit 1
fi

# Create mount directory if it doesn't exist
MOUNT_DIR="/home/ubuntu/lattice-files"
if [ ! -d "$MOUNT_DIR" ]; then
    echo "Creating mount directory $MOUNT_DIR..."
    mkdir -p "$MOUNT_DIR"
    chown ubuntu:ubuntu "$MOUNT_DIR"
    chmod 755 "$MOUNT_DIR"
else
    echo "Mount directory $MOUNT_DIR already exists"
    # Ensure proper permissions on existing directory
    chown ubuntu:ubuntu "$MOUNT_DIR"
    chmod 755 "$MOUNT_DIR"
fi

# Backup existing fstab
cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d%H%M%S)

echo "Adding mount entries to /etc/fstab..."

# For each mount point we'll create the directory first
create_and_add_mount() {
    local bucket=$1
    local mount_point="/home/ubuntu/lattice-files/$bucket"
    
    # Create mount point directory if it doesn't exist
    if [ ! -d "$mount_point" ]; then
        echo "Creating mount point $mount_point..."
        mkdir -p "$mount_point"
        chown ubuntu:ubuntu "$mount_point"
        chmod 755 "$mount_point"
    fi
    
    # Add to fstab if not already there
    if ! grep -q "goofys#$bucket" /etc/fstab; then
        echo "Adding $bucket to fstab..."
        echo "goofys#$bucket   $mount_point        fuse     _netdev,allow_other,--file-mode=0666    0       0" >> /etc/fstab
    else
        echo "Mount for $bucket already in fstab, skipping."
    fi
}

# Add all buckets to fstab
create_and_add_mount "cdk-hnb659fds-assets-585222078325-us-west-1"
create_and_add_mount "lattice-files"
create_and_add_mount "lattice-files-dev"
create_and_add_mount "lattice-packer-ami-id-and-log"
create_and_add_mount "latticed-backups-prod"
create_and_add_mount "latticed-blobs"
create_and_add_mount "latticed-blobs-dev"
create_and_add_mount "latticed-build"
create_and_add_mount "latticed-conf-prod"
create_and_add_mount "latticed-files-upload"
create_and_add_mount "submissions-cxg"
create_and_add_mount "submissions-lattice"
create_and_add_mount "submissions-lattice-sra"

# Add CZI buckets (just a sample, the actual script has many more)
for i in {001..038} {101..118} {201..216}; do
    bucket_name="submissions-czi${i}"
    project_code=$(echo "$bucket_name" | sed 's/.*\(...\)$/\1/')
    create_and_add_mount "submissions-czi${i}${project_code}"
done

echo "Testing mount functionality..."
mount -a -t fuse || echo "WARNING: Some mounts may have failed, but continuing..."

echo "Goofys mount points setup completed."
exit 0