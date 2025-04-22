#!/bin/bash
set -ex

# Create directory for Rust project
RUST_PROJECT_DIR="/opt/checkfiles/rust"
sudo mkdir -p $RUST_PROJECT_DIR
cd $RUST_PROJECT_DIR

# Copy Cargo.toml, Cargo.lock and source files from the build context
sudo cp /tmp/build/Cargo.toml .
sudo cp /tmp/build/Cargo.lock .
sudo cp -r /tmp/build/src .

# Verify Rust version
REQUIRED_RUST_VERSION=$(jq -r .rust_version /tmp/build/rust-dependencies.json)
CURRENT_RUST_VERSION=$(rustc --version | cut -d ' ' -f 2)

if [ "$CURRENT_RUST_VERSION" != "$REQUIRED_RUST_VERSION" ]; then
    echo "Incorrect Rust version. Required: $REQUIRED_RUST_VERSION, Found: $CURRENT_RUST_VERSION"
    exit 1
fi

# Source Rust environment
source "$HOME/.cargo/env"

# Verify cargo dependencies match lock file
if ! cargo verify-project --manifest-path $RUST_PROJECT_DIR/Cargo.toml; then
    echo "Cargo.toml verification failed"
    exit 1
fi

# Build in release mode
cargo build --release

# Create a virtual environment and install the Rust package
VENV_DIR="/opt/checkfiles/venv"
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

# Create directory for storing compiled artifacts
sudo mkdir -p /opt/checkfiles/lib
sudo cp target/release/libfastq_validator.* /opt/checkfiles/lib/

# Set appropriate permissions
sudo chown -R root:root /opt/checkfiles
sudo chmod -R 755 /opt/checkfiles 