#!/bin/bash
set -ex

# Remove existing Rust installation if it exists
if [ -d "/usr/local/bin/rustc" ]; then
    sudo rm -f /usr/local/bin/cargo*
    sudo rm -f /usr/local/bin/rust*
    sudo rm -f /usr/local/bin/clippy-driver
    sudo rm -f /usr/local/bin/rls
fi

# Install Rust using rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Add Rust to PATH for the current session
source "$HOME/.cargo/env"

# Install specific toolchain version 1.70.0
rustup install 1.70.0
rustup default 1.70.0

# Install additional components
rustup component add rustfmt
rustup component add clippy

# Verify installation
cargo --version
rustc --version

# Make cargo available to all users (using force flag)
sudo ln -sf $HOME/.cargo/bin/* /usr/local/bin/