#!/bin/bash
set -ex

# Create directory for checkfiles package
PYTHON_PACKAGE_DIR="/opt/checkfiles/python"
sudo mkdir -p $PYTHON_PACKAGE_DIR
sudo chown -R ubuntu:ubuntu $PYTHON_PACKAGE_DIR

# Copy Python files from build context
sudo cp -r /tmp/build/src $PYTHON_PACKAGE_DIR/
sudo cp /tmp/build/setup.py $PYTHON_PACKAGE_DIR/
sudo cp /tmp/build/pyproject.toml $PYTHON_PACKAGE_DIR/

# Create a virtual environment
VENV_DIR="/opt/checkfiles/venv"
sudo mkdir -p $VENV_DIR
sudo chown -R ubuntu:ubuntu $VENV_DIR

python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Install the package in development mode
cd $PYTHON_PACKAGE_DIR
pip install -e .

# Make the package available system-wide
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
DIST_PACKAGES_DIR="/usr/local/lib/python${PYTHON_VERSION}/dist-packages"

sudo mkdir -p $DIST_PACKAGES_DIR
# Create a system-wide entry for the package
sudo tee $DIST_PACKAGES_DIR/checkfiles.pth > /dev/null << EOF
$PYTHON_PACKAGE_DIR
EOF

# Set final permissions
sudo chown -R root:root /opt/checkfiles
sudo chmod -R 755 /opt/checkfiles

# Verify installation
python3 -c "from src.validators.fastq import FastqValidator; print('FastqValidator installed successfully')" 