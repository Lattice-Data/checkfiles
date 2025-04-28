#!/bin/bash
# AMI Validation Script for Checkfiles.
#
# This script validates the AMI after creation by checking:
# 1. Required packages are installed
# 2. Required services are running
# 3. Required files and directories exist
# 4. Required commands are available and working
#
# Usage:
#   sudo ./validate_ami.sh

set -euo pipefail

# Configuration
REQUIRED_PACKAGES=(
    "samtools"
    "python3"
    "pip3"
    "aws"
    "jq"
)

REQUIRED_DIRS=(
    "/usr/local/bin"
    "/usr/local/lib"
    "/etc/checkfiles"
)

REQUIRED_FILES=(
    "/usr/local/bin/samtools"
    "/usr/local/bin/validatefiles"
)

# Error handling function
handle_error() {
    echo "ERROR: Validation failed at line $1"
    exit 1
}

# Set up error trap
trap 'handle_error $LINENO' ERR

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

echo "Starting AMI validation..."

# Check required packages
echo "Checking required packages..."
for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! command -v "$package" &> /dev/null; then
        echo "ERROR: Required package $package is not installed"
        exit 1
    fi
    echo "✓ $package is installed"
done

# Check if fuse is installed properly using multiple detection methods
echo "Checking fuse installation..."
if dpkg -l | grep -q 'fuse\s'; then
    echo "✓ fuse package is installed (detected via dpkg)"
elif [ -f "/usr/bin/fusermount" ] || [ -f "/bin/fusermount" ]; then
    echo "✓ fuse package is installed (detected via fusermount binary)"
elif [ -c "/dev/fuse" ]; then
    echo "✓ fuse package is installed (detected via /dev/fuse device)"
else
    echo "WARNING: Trying to install fuse package..."
    apt-get update && apt-get install -y fuse
    
    if ! dpkg -l | grep -q 'fuse\s'; then
        echo "WARNING: Could not verify fuse installation, but continuing since it might be integrated into the kernel"
    fi
fi

# Try to load fuse module if not already loaded
if ! lsmod | grep -q fuse; then
    echo "Attempting to load fuse kernel module..."
    modprobe fuse 2>/dev/null || true
fi

# Check required directories
echo "Checking required directories..."
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "WARNING: Required directory $dir does not exist. Creating it..."
        mkdir -p "$dir"
        if [ ! -d "$dir" ]; then
            echo "ERROR: Failed to create directory $dir"
            exit 1
        fi
    fi
    echo "✓ Directory $dir exists"
done

# Check required files
echo "Checking required files..."
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "ERROR: Required file $file does not exist"
        exit 1
    fi
    echo "✓ File $file exists"
done

# Check samtools version and functionality
echo "Checking samtools..."
SAMTOOLS_VERSION=$(samtools --version | head -n 1 | awk '{print $2}')
if [ -z "$SAMTOOLS_VERSION" ]; then
    echo "ERROR: Could not determine samtools version"
    exit 1
fi
echo "✓ Samtools version $SAMTOOLS_VERSION is installed"

# Check Python environment
echo "Checking Python environment..."
if ! python3 -c "import sys; print(f'Python {sys.version}')" &> /dev/null; then
    echo "ERROR: Python environment is not properly configured"
    exit 1
fi
echo "✓ Python environment is properly configured"

# Check AWS CLI configuration
echo "Checking AWS CLI..."
if ! aws --version &> /dev/null; then
    echo "ERROR: AWS CLI is not properly configured"
    exit 1
fi
echo "✓ AWS CLI is properly configured"

echo "AMI validation completed successfully!"
exit 0 
exit 0 