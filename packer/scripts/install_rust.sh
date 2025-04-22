   #!/bin/bash
   set -ex

   # Install Rust using rustup
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

   # Add Rust to PATH for the current session
   source "$HOME/.cargo/env"

   # Install specific toolchain version (recommended for reproducibility)
   rustup default stable

   # Install additional components if needed
   rustup component add rustfmt
   rustup component add clippy

   # Verify installation
   cargo --version
   rustc --version