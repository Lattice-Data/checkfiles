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

# Create necessary directories
echo "Setting up package directories..."
sudo mkdir -p "${SITE_PACKAGES}/checkfiles"
sudo mkdir -p "${SITE_PACKAGES}/checkfiles/validators"
sudo chmod -R 777 "${SITE_PACKAGES}/checkfiles"

# Create __init__.py files
sudo touch "${SITE_PACKAGES}/checkfiles/__init__.py"
sudo touch "${SITE_PACKAGES}/checkfiles/validators/__init__.py"

# Install the package in development mode
echo "Installing package in development mode..."
cd /opt/checkfiles || { echo "ERROR: Cannot change to /opt/checkfiles directory"; exit 1; }

# Verify Python setup files exist
if [ ! -f setup.py ] && [ ! -f pyproject.toml ]; then
    echo "ERROR: Neither setup.py nor pyproject.toml found in /opt/checkfiles"
    exit 1
fi

sudo pip3 install -e .

# Verify installation
echo "Verifying installation..."
python3 -c "import checkfiles; import checkfiles.validators; print('Package installed successfully')" || {
    echo "ERROR: Failed to import checkfiles package"
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