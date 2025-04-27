#!/bin/bash
"""
Validator modules setup script for Checkfiles.

This script sets up the validator modules for the Checkfiles application.
It copies validator modules from the build directory to the appropriate
Python site-packages location and creates necessary symbolic links.

Usage:
  sudo ./setup_validator_modules.sh
"""

set -ex

# Determine Python site-packages directory
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SITE_PACKAGES="/usr/local/lib/python${PYTHON_VERSION}/dist-packages"
SRC_DIR="${SITE_PACKAGES}/src"
VALIDATORS_DIR="${SITE_PACKAGES}/validators"

# Print the content of build directory for debugging
echo "Contents of /tmp/build:"
ls -la /tmp/build
echo "Contents of /tmp/build/src:"
ls -la /tmp/build/src || echo "src directory not found"

# Ensure validators directory exists and has proper permissions
sudo mkdir -p /tmp/build/src/validators
sudo chmod 777 /tmp/build/src/validators

# Create base validators.__init__.py file if needed
if [ ! -f "/tmp/build/src/validators/__init__.py" ]; then
    sudo touch /tmp/build/src/validators/__init__.py
fi

# Copy all validators files from build to site-packages
echo "Copying validators files"
sudo cp -r /tmp/build/src/validators/* $VALIDATORS_DIR/ || echo "No files in validators directory to copy"

# Create symbolic links to connect src.validators with validators
echo "Creating symbolic links for validator modules"
for file in $(find ${VALIDATORS_DIR} -type f -name "*.py" 2>/dev/null || echo ""); do
    base_file=$(basename "$file")
    sudo ln -sf "$file" "${SRC_DIR}/validators/${base_file}"
    echo "Created link for $base_file"
done

# Handle checkfiles.py main script if it exists
if [ -f "/tmp/build/src/checkfiles.py" ]; then
    echo "Setting up checkfiles.py main script"
    sudo cp /tmp/build/src/checkfiles.py "${SITE_PACKAGES}/checkfiles.py"
    sudo chmod 755 "${SITE_PACKAGES}/checkfiles.py"
    sudo ln -sf "${SITE_PACKAGES}/checkfiles.py" "${SRC_DIR}/checkfiles.py"
    echo "checkfiles.py installed successfully"
else
    echo "Warning: checkfiles.py not found in build directory"
fi

# Verify the installation with basic import test
echo "Verifying installation with basic import test"
python3 -c "import src; import validators; print('Modules imported successfully')" || echo "Basic import test failed but continuing"

echo "Validator modules setup completed." 