#!/bin/bash
"""
Python dependencies installer for Checkfiles.

This script installs Python dependencies required for the Checkfiles application.
It handles both system-level dependencies and Python packages.

Usage:
  sudo ./install_python_dependencies.sh
"""

set -ex

# Print diagnostic information
echo "Installing Python dependencies for Checkfiles"
echo "Python version: $(python3 --version)"
echo "Pip version: $(pip3 --version)"

# Determine Python site-packages directory
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SITE_PACKAGES="/usr/local/lib/python${PYTHON_VERSION}/dist-packages"
sudo mkdir -p $SITE_PACKAGES

# Install required system packages
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    build-essential \
    libffi-dev \
    libssl-dev

# Install AWS SDK
echo "Installing AWS SDK..."
pip3 install --no-cache-dir \
    botocore==1.31.17 \
    awscli==1.29.17 \
    boto3==1.28.17

# Install core Python packages
echo "Installing core Python packages..."
pip3 install --no-cache-dir \
    pytest==7.4.0 \
    pytest-cov==4.1.0 \
    black==23.7.0 \
    ruff==0.0.282 \
    mypy==1.5.1 \
    types-requests==2.31.0 \
    types-boto3==1.0.2 \
    numpy==1.24.3 \
    crcmod==1.7 \
    h5py==3.10.0

# Create src package directory if it doesn't exist
echo "Setting up package directories..."
SRC_DIR="${SITE_PACKAGES}/src"
sudo mkdir -p $SRC_DIR
sudo chmod 777 $SRC_DIR

# Create an __init__.py file in the src package
sudo touch "${SRC_DIR}/__init__.py"

# Create validators directory in site packages
VALIDATORS_DIR="${SITE_PACKAGES}/validators"
sudo mkdir -p $VALIDATORS_DIR
sudo chmod 777 $VALIDATORS_DIR
sudo touch "${VALIDATORS_DIR}/__init__.py"

# Create src/validators structure
sudo mkdir -p "${SRC_DIR}/validators"
sudo chmod 777 "${SRC_DIR}/validators"
sudo touch "${SRC_DIR}/validators/__init__.py"

echo "Python dependencies installation completed successfully." 