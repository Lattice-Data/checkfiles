#!/bin/bash
set -ex

sudo apt-get update
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
    awscli \
    jq \
    pkg-config \
    libssl-dev

# Add Rust binary directory to system-wide PATH
echo 'export PATH="$HOME/.cargo/bin:$PATH"' | sudo tee /etc/profile.d/rust.sh

# Make cargo binaries available to all users
sudo chmod +rx /etc/profile.d/rust.sh