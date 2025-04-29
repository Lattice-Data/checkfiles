#!/bin/bash
set -euo pipefail

echo "Validator modules setup script for Checkfiles."
echo ""
echo "This script sets up the validator modules by:"
echo "1. Installing the Python package in development mode"
echo "2. Creating necessary directories"
echo "3. Creating validator stubs"
echo "4. Verifying the installation"
echo ""

# Create and set up /opt/checkfiles directory
sudo mkdir -p /opt/checkfiles
sudo chmod -R 777 /opt/checkfiles

# Copy files from /tmp/build to /opt/checkfiles
if [ -d /tmp/build ]; then
    echo "Copying files from /tmp/build to /opt/checkfiles..."
    sudo cp -r /tmp/build/* /opt/checkfiles/
    sudo chmod -R 777 /opt/checkfiles
else
    echo "ERROR: /tmp/build directory not found"
    exit 1
fi

# List directory contents for debugging
echo "Checking /opt/checkfiles contents:"
ls -la /opt/checkfiles

# Set up environment
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
SITE_PACKAGES="/usr/local/lib/python${PYTHON_VERSION}/dist-packages"

# Create necessary directories in site-packages
echo "Setting up package directories in site-packages..."
sudo mkdir -p "${SITE_PACKAGES}/src"
sudo mkdir -p "${SITE_PACKAGES}/src/validators"
sudo mkdir -p "${SITE_PACKAGES}/src/validators/fastq"
sudo chmod -R 777 "${SITE_PACKAGES}/src"

# Create necessary directories in /opt/checkfiles
echo "Setting up package directories in /opt/checkfiles..."
sudo mkdir -p "/opt/checkfiles/src/validators"
sudo mkdir -p "/opt/checkfiles/src/validators/fastq"
sudo chmod -R 777 "/opt/checkfiles/src"

# Create __init__.py files in site-packages
sudo touch "${SITE_PACKAGES}/src/__init__.py"
sudo touch "${SITE_PACKAGES}/src/validators/__init__.py"
sudo touch "${SITE_PACKAGES}/src/validators/fastq/__init__.py"

# Create __init__.py files in /opt/checkfiles
sudo touch "/opt/checkfiles/src/__init__.py"
sudo touch "/opt/checkfiles/src/validators/__init__.py"
sudo touch "/opt/checkfiles/src/validators/fastq/__init__.py"

# Install the package in development mode
echo "Installing package in development mode..."
cd /opt/checkfiles || { echo "ERROR: Cannot change to /opt/checkfiles directory"; exit 1; }

# Verify Python setup files exist
if [ ! -f setup.py ] && [ ! -f pyproject.toml ]; then
    echo "ERROR: Neither setup.py nor pyproject.toml found in /opt/checkfiles"
    exit 1
fi

sudo pip3 install -e .

# Create proper imports in fastq.py
echo "Creating fastq.py for proper imports..."
cat > /opt/checkfiles/src/validators/fastq.py << 'EOF'
"""
FASTQ file and stream validator with pure Python implementation.

This module provides the FastqValidator class for validating FASTQ files 
and streams. Import and usage remains the same for backward compatibility,
but implementation has been refactored into separate modules.
"""

from .fastq.validator import FastqValidator

__all__ = ["FastqValidator"]
EOF

# Copy fastq.py to site-packages as well
sudo cp /opt/checkfiles/src/validators/fastq.py "${SITE_PACKAGES}/src/validators/fastq.py"

# Ensure correct permissions
sudo chmod -R 777 "${SITE_PACKAGES}/src"
sudo chmod -R 777 "/opt/checkfiles/src"

# Verify installation by trying to import from src.validators
echo "Verifying installation..."
python3 -c "import src.validators; print('src.validators package imported successfully')" || {
    echo "ERROR: Failed to import src.validators package"
    exit 1
}

python3 -c "from src.validators.fastq import FastqValidator; print('FastqValidator imported successfully')" || {
    echo "ERROR: Failed to import FastqValidator from src.validators.fastq"
    echo "This is critical for the operation of the checkfiles software."
    exit 1
}

# Run tests only if tests directory exists
echo "Running tests..."
if [ -d "tests" ]; then
    cd /opt/checkfiles || exit 1
    python3 -m pytest tests/
else
    echo "NOTICE: No tests directory found, skipping tests"
fi

echo "Validator modules setup completed." 