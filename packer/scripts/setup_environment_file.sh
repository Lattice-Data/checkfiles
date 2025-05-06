#!/bin/bash
set -ex

echo "==== Setting up checkfiles environment file ===="

# Set up environment variables
echo 'export PYTHONPATH="${PYTHONPATH}:/home/ubuntu/checkfiles"' | sudo tee -a /etc/profile.d/checkfiles.sh
echo 'export PYTHONUNBUFFERED=1' | sudo tee -a /etc/profile.d/checkfiles.sh
echo 'export DEBIAN_FRONTEND=noninteractive' | sudo tee -a /etc/profile.d/checkfiles.sh
echo 'export CHECKFILES_LOG_DIR=/home/ubuntu/checkfiles' | sudo tee -a /etc/profile.d/checkfiles.sh

# Set permissions
sudo chmod 644 /etc/profile.d/checkfiles.sh

echo "Environment setup completed."
