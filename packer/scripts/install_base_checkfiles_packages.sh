#!/bin/bash
set -ex

# Update package lists
sudo apt-get update

# Install base packages
sudo apt-get -y install \
    python3-pip \
    python3-venv \
    build-essential \
    libbz2-dev \
    liblzma-dev \
    curl \
    zlib1g-dev \
    libsqlite3-dev \
    fuse \
    libfuse-dev \
    awscli \
    jq \
    pkg-config \
    libssl-dev

# Check if fuse was installed correctly
if ! dpkg -l | grep -q fuse; then
    echo "ERROR: fuse package installation failed, trying again..."
    sudo apt-get -y install fuse
    
    if ! dpkg -l | grep -q fuse; then
        echo "ERROR: fuse package installation failed again"
        exit 1
    fi
fi

# Ensure fuse module is loaded
if ! lsmod | grep -q fuse; then
    echo "Loading fuse kernel module..."
    sudo modprobe fuse
    
    if ! lsmod | grep -q fuse; then
        echo "WARNING: Could not load fuse kernel module, but continuing..."
    fi
fi

# Create necessary fuse configuration
echo "Configuring fuse..."
if [ ! -d "/etc/checkfiles" ]; then
    sudo mkdir -p /etc/checkfiles
fi

# Create user_allow_other fuse configuration to allow non-root users to use fuse
sudo sh -c 'echo "user_allow_other" > /etc/fuse.conf'

echo "Base package installation completed."