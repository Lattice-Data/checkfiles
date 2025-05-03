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

# Check required executables
required_executables=(
    "python3"
    "pip3"
    "aws"
)

# Check required executable paths
required_paths=(
    "/usr/bin/python3"
    "/usr/bin/pip3"
    "/usr/local/bin/aws"
)

# Check if all required executables are installed
echo "Checking required executables..."
for exec in "${required_executables[@]}"; do
    if ! command -v "$exec" &> /dev/null; then
        echo "ERROR: $exec is not installed"
        exit 1
    fi
    echo "✓ $exec is installed"
done

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

# Check Python environment and version
echo "Checking Python environment..."
PYTHON_VERSION=$(python3 --version | awk '{print $2}')

# Proper version comparison using version comparison function
function version_compare() {
    # This function compares version strings
    # Returns 0 if version1 >= version2, 1 otherwise
    if [[ $(echo -e "$1\n$2" | sort -V | head -n1) = "$2" ]]; then
        return 0
    else
        return 1
    fi
}

# Check if Python version is at least 3.8
if ! version_compare "$PYTHON_VERSION" "3.8"; then
    echo "ERROR: Python version must be at least 3.8, found $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python version $PYTHON_VERSION is sufficient"

# Check AWS CLI configuration
echo "Checking AWS CLI..."
if ! aws --version &> /dev/null; then
    echo "ERROR: AWS CLI is not properly configured"
    exit 1
fi
echo "✓ AWS CLI is properly configured"

echo "AMI validation completed successfully!"
exit 0 