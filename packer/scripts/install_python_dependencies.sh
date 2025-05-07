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

# Install system packages
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    build-essential \
    libffi-dev \
    libssl-dev

# Install AWS CLI with specific versions (kept separate for AWS compatibility)
echo "Installing AWS SDK..."
pip3 install --no-cache-dir \
    botocore==1.31.17 \
    awscli==1.29.17 \
    boto3==1.28.17

# Install package with all dependencies for AMI
echo "Installing package with AMI dependencies..."
cd /opt/checkfiles || { echo "ERROR: Cannot change to /opt/checkfiles directory"; exit 1; }
# Install with AMI-specific dependencies
pip3 install --no-cache-dir ".[ami]"

# Ensure core packages are installed with correct versions
pip3 install --no-cache-dir crcmod==1.7

echo "Python dependencies installation completed successfully." 