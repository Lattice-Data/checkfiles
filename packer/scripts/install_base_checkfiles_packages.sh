#!/bin/bash
set -ex

# Update package lists
sudo apt-get update

# Install base packages (removed fuse-specific packages)
sudo apt-get -y install \
    python3-pip \
    python3-venv \
    build-essential \
    libbz2-dev \
    liblzma-dev \
    curl \
    zlib1g-dev \
    libsqlite3-dev \
    awscli \
    jq \
    pkg-config \
    libssl-dev

echo "Base package installation completed."