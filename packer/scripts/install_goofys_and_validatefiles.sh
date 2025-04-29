#!/bin/bash
set -ex

# Consolidated FUSE configuration script for Checkfiles
# This is now the central place for all FUSE-related setup
echo "=== Installing and configuring FUSE components ==="

# Install fuse package and dependencies
echo "Installing fuse package and dependencies..."
sudo apt-get update
sudo apt-get install -y fuse libfuse2 libfuse-dev

# Create fuse.conf file with user_allow_other option
echo "Configuring fuse..."
sudo sh -c 'echo "user_allow_other" > /etc/fuse.conf'
sudo chmod 644 /etc/fuse.conf

# Ensure fuse module is loaded
if ! lsmod | grep -q fuse; then
    echo "Loading fuse kernel module..."
    sudo modprobe fuse
    
    if ! lsmod | grep -q fuse; then
        echo "WARNING: Could not load fuse kernel module, but continuing..."
    fi
fi

# Verify fuse installation using multiple methods
echo "Verifying fuse installation..."
if ! dpkg -l | grep -q 'fuse\s'; then
    echo "WARNING: fuse package not detected with dpkg, trying alternative verification"
    if [ ! -f "/usr/bin/fusermount" ] && [ ! -f "/bin/fusermount" ] && [ ! -c "/dev/fuse" ]; then
        echo "ERROR: Failed to verify fuse installation"
        exit 1
    fi
fi

# Create necessary fuse directories
echo "Creating necessary fuse directories..."
if [ ! -d "/etc/checkfiles" ]; then
    sudo mkdir -p /etc/checkfiles
    sudo chmod 755 /etc/checkfiles
fi

# Install goofys
echo "Installing goofys..."
sudo curl -sS -L -o /usr/local/bin/goofys https://github.com/kahing/goofys/releases/download/v0.24.0/goofys
sudo chmod +x /usr/local/bin/goofys

# Install validateFiles
echo "Installing validateFiles..."
sudo curl -sS -L -o /usr/local/bin/validatefiles https://raw.githubusercontent.com/IGVF-DACC/validateFiles/main/validateFiles
sudo chmod +x /usr/local/bin/validatefiles

# Create symbolic links to ensure consistent capitalization
sudo ln -sf /usr/local/bin/validatefiles /usr/local/bin/validateFiles

# Verify installations
echo "Verifying installations..."
which goofys || { echo "goofys installation failed"; exit 1; }
which validatefiles || { echo "validatefiles installation failed"; exit 1; }

echo "FUSE configuration and tool installation completed successfully."
