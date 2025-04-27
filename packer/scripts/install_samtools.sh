#!/bin/bash
# Script to install samtools for BAM/CRAM validation

set -e

echo "Installing samtools dependencies..."
apt-get update
apt-get install -y \
    build-essential \
    wget \
    bzip2 \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev

echo "Downloading and installing samtools..."
SAMTOOLS_VERSION="1.17"
wget https://github.com/samtools/samtools/releases/download/${SAMTOOLS_VERSION}/samtools-${SAMTOOLS_VERSION}.tar.bz2
tar -xjf samtools-${SAMTOOLS_VERSION}.tar.bz2
cd samtools-${SAMTOOLS_VERSION}
./configure --prefix=/usr/local
make
make install
cd ..
rm -rf samtools-${SAMTOOLS_VERSION} samtools-${SAMTOOLS_VERSION}.tar.bz2

# Verify installation
echo "Verifying samtools installation..."
samtools --version

echo "Samtools installation completed." 