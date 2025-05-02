#!/bin/bash
set -e

echo "==== Setting up checkfiles environment file ===="

# Create environment file
echo "Creating .env_checkfiles file..."
cat > /home/ubuntu/.env_checkfiles << 'EOL'
export PYTHONPATH=/home/ubuntu/checkfiles:$PYTHONPATH
export CHECKFILES_LOG_DIR=/home/ubuntu/checkfiles
EOL

# Set proper permissions
chown ubuntu:ubuntu /home/ubuntu/.env_checkfiles
chmod 644 /home/ubuntu/.env_checkfiles

# Add to .bashrc to source it automatically 
grep -q "source /home/ubuntu/.env_checkfiles" /home/ubuntu/.bashrc || \
    echo "source /home/ubuntu/.env_checkfiles" >> /home/ubuntu/.bashrc

echo "Environment setup complete!"
