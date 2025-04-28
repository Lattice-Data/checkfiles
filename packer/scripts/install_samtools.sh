#!/bin/bash
# Samtools installation script for Checkfiles.
#
# This script installs samtools for BAM/CRAM file validation.
# It handles dependency installation, compilation from source,
# and verification of successful installation.
#
# Usage:
#   sudo ./install_samtools.sh

set -euo pipefail

# Configuration
SAMTOOLS_VERSION="1.21"
INSTALL_PREFIX="/usr/local"
BUILD_DIR="/tmp/samtools_build"
LOG_FILE="/tmp/samtools_install.log"

# Ensure we're running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

echo "Installing samtools ${SAMTOOLS_VERSION}..."

# Create log file
touch "$LOG_FILE"
exec &> >(tee -a "$LOG_FILE")

# Error handling function
handle_error() {
    echo "ERROR: Samtools installation failed at line $1"
    echo "Check $LOG_FILE for details"
    exit 1
}

# Set up error trap
trap 'handle_error $LINENO' ERR

# Ensure clean build environment
if [ -d "$BUILD_DIR" ]; then
    echo "Removing previous build directory..."
    rm -rf "$BUILD_DIR"
fi
mkdir -p "$BUILD_DIR"

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
    libssl-dev \
    libncurses5-dev \
    libncursesw5-dev

echo "Downloading samtools ${SAMTOOLS_VERSION}..."
cd "$BUILD_DIR"
wget "https://github.com/samtools/samtools/releases/download/${SAMTOOLS_VERSION}/samtools-${SAMTOOLS_VERSION}.tar.bz2"

echo "Extracting samtools archive..."
tar -xjf "samtools-${SAMTOOLS_VERSION}.tar.bz2"
cd "samtools-${SAMTOOLS_VERSION}"

echo "Configuring samtools..."
./configure --prefix=$INSTALL_PREFIX

echo "Compiling samtools..."
make -j$(nproc)

echo "Installing samtools..."
make install

# Clean up build files
cd ..
rm -rf "samtools-${SAMTOOLS_VERSION}" "samtools-${SAMTOOLS_VERSION}.tar.bz2"

# Verify installation
echo "Verifying samtools installation..."
if ! command -v samtools &> /dev/null; then
    echo "ERROR: samtools command not found after installation"
    exit 1
fi

INSTALLED_VERSION=$(samtools --version | head -n 1 | awk '{print $2}')
if [ "$INSTALLED_VERSION" != "$SAMTOOLS_VERSION" ]; then
    echo "ERROR: Expected samtools version ${SAMTOOLS_VERSION}, but found ${INSTALLED_VERSION}"
    exit 1
fi

echo "Samtools ${SAMTOOLS_VERSION} installation completed successfully."
echo "Version information:"
samtools --version | head -n 2 