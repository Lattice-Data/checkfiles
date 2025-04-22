#!/bin/bash
set -ex

# Install Rust using rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Add Rust to PATH for the current session
source "$HOME/.cargo/env"

# Install specific toolchain version (will be verified against rust-dependencies.json)
rustup default stable

# Install additional components
rustup component add rustfmt
rustup component add clippy

# Verify installation
cargo --version
rustc --version

# Make cargo available to all users
sudo ln -s $HOME/.cargo/bin/* /usr/local/bin/