#!/bin/bash
set -ex

# Create directory for Rust project
RUST_PROJECT_DIR="/opt/checkfiles/rust"
sudo mkdir -p $RUST_PROJECT_DIR
cd $RUST_PROJECT_DIR

# Copy Cargo.toml and source files from the build context
sudo cp /tmp/build/Cargo.toml .
sudo cp -r /tmp/build/src .

# Set ownership of the project directory to the current user
sudo chown -R ubuntu:ubuntu $RUST_PROJECT_DIR

# Verify Rust version
REQUIRED_RUST_VERSION=$(jq -r .rust_version /tmp/build/rust-dependencies.json)
CURRENT_RUST_VERSION=$(rustc --version | cut -d ' ' -f 2)

if [ "$CURRENT_RUST_VERSION" != "$REQUIRED_RUST_VERSION" ]; then
    echo "Incorrect Rust version. Required: $REQUIRED_RUST_VERSION, Found: $CURRENT_RUST_VERSION"
    exit 1
fi

# Source Rust environment
source "$HOME/.cargo/env"

# Generate new Cargo.lock file
cargo generate-lockfile

# Verify cargo dependencies
if ! cargo verify-project --manifest-path $RUST_PROJECT_DIR/Cargo.toml; then
    echo "Cargo.toml verification failed"
    exit 1
fi

# Build in release mode
cargo build --release

# Create a virtual environment and install the Rust package
VENV_DIR="/opt/checkfiles/venv"
sudo mkdir -p $VENV_DIR
sudo chown -R ubuntu:ubuntu $VENV_DIR

python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Install maturin for Rust-Python bindings
pip install maturin

# Build and install the Rust package
cd $RUST_PROJECT_DIR
maturin build --release
pip install target/wheels/*.whl

# Cleanup build artifacts but keep the compiled library
sudo rm -rf target/debug target/release/deps target/release/build

# Create directory for storing compiled artifacts and set final permissions
sudo mkdir -p /opt/checkfiles/lib
sudo cp target/release/libfastq_validator.* /opt/checkfiles/lib/
sudo chown -R root:root /opt/checkfiles
sudo chmod -R 755 /opt/checkfiles

# Create Python package structure
PYTHON_PACKAGE_DIR="/opt/checkfiles/python"
sudo mkdir -p $PYTHON_PACKAGE_DIR/fastq_validator
sudo chown -R ubuntu:ubuntu $PYTHON_PACKAGE_DIR  # Set ownership before creating files
sudo touch $PYTHON_PACKAGE_DIR/fastq_validator/__init__.py

# Create a simple Python module that loads the Rust library
sudo tee $PYTHON_PACKAGE_DIR/fastq_validator/__init__.py > /dev/null << EOF
import os
import sys
import ctypes

# Add the lib directory to the library search path
lib_dir = "/opt/checkfiles/lib"
if lib_dir not in sys.path:
    sys.path.append(lib_dir)

# Load the Rust library
try:
    lib = ctypes.CDLL(os.path.join(lib_dir, "libfastq_validator.so"))
    # Define the Rust functions we want to use
    lib.validate_fastq.argtypes = [ctypes.c_char_p]
    lib.validate_fastq.restype = ctypes.c_bool
    lib.fastq_stats.argtypes = [ctypes.c_char_p]
    lib.fastq_stats.restype = ctypes.c_void_p
except Exception as e:
    raise ImportError(f"Failed to load Rust library: {e}")

# Make the library available to other modules
fastq_validator = lib
EOF

# Create setup.py
sudo tee $PYTHON_PACKAGE_DIR/setup.py > /dev/null << EOF
from setuptools import setup, find_packages

setup(
    name="fastq_validator",
    version="0.1.0",
    packages=find_packages(),
    package_data={
        'fastq_validator': ['*.so'],
    },
    include_package_data=True,
    zip_safe=False,
)
EOF

# Install the package in development mode
cd $PYTHON_PACKAGE_DIR
# Make sure the virtual environment is owned by ubuntu
sudo chown -R ubuntu:ubuntu $VENV_DIR
pip install -e .

# Create a symlink to make the package available system-wide
# First, find the correct Python dist-packages directory
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
DIST_PACKAGES_DIR="/usr/local/lib/python${PYTHON_VERSION}/dist-packages"
sudo mkdir -p $DIST_PACKAGES_DIR
sudo ln -sf $PYTHON_PACKAGE_DIR/fastq_validator $DIST_PACKAGES_DIR/fastq_validator

# Set final permissions
sudo chown -R root:root /opt/checkfiles
sudo chmod -R 755 /opt/checkfiles 