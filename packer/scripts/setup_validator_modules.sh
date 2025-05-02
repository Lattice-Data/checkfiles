#!/bin/bash
# Centralized validator modules setup script for Checkfiles
# This is the main script for setting up Python module structure
set -euo pipefail

echo "=== Validator modules setup script for Checkfiles ==="
echo "This script is the central location for all Python module setup"
echo "It handles:"
echo "1. Installing the Python package in development mode"
echo "2. Creating necessary directories in a consistent way"
echo "3. Setting up symbolic links for module discovery"
echo "4. Verifying the installation"
echo ""

# Create and set up /opt/checkfiles directory
sudo mkdir -p /opt/checkfiles
sudo chmod -R 777 /opt/checkfiles

# Copy files from /tmp/build to /opt/checkfiles
if [ -d /tmp/build ]; then
    echo "Copying files from /tmp/build to /opt/checkfiles..."
    sudo cp -r /tmp/build/* /opt/checkfiles/
    sudo chmod -R 777 /opt/checkfiles
else
    echo "ERROR: /tmp/build directory not found"
    exit 1
fi

# List directory contents for debugging
echo "Checking /opt/checkfiles contents:"
ls -la /opt/checkfiles

# Set up environment
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
# Standardize on a single site-packages location
SITE_PACKAGES="/usr/local/lib/python${PYTHON_VERSION}/dist-packages"

# Create necessary directories with standardized paths
echo "Setting up standardized package directories..."
# Main source directories
sudo mkdir -p "${SITE_PACKAGES}/src"
sudo mkdir -p "${SITE_PACKAGES}/src/validators"
sudo mkdir -p "${SITE_PACKAGES}/src/validators/fastq"
sudo mkdir -p "${SITE_PACKAGES}/src/utils"
sudo mkdir -p "${SITE_PACKAGES}/src/utils/helpers"
sudo chmod -R 777 "${SITE_PACKAGES}/src"

# Create the same structure in /opt/checkfiles for development
sudo mkdir -p "/opt/checkfiles/src/validators"
sudo mkdir -p "/opt/checkfiles/src/validators/fastq"
sudo mkdir -p "/opt/checkfiles/src/utils"
sudo mkdir -p "/opt/checkfiles/src/utils/helpers"
sudo chmod -R 777 "/opt/checkfiles/src"

# Create __init__.py files in site-packages
echo "Creating __init__.py files for Python packages..."
sudo touch "${SITE_PACKAGES}/src/__init__.py"
sudo touch "${SITE_PACKAGES}/src/validators/__init__.py"
sudo touch "${SITE_PACKAGES}/src/validators/fastq/__init__.py"
sudo touch "${SITE_PACKAGES}/src/utils/__init__.py"
sudo touch "${SITE_PACKAGES}/src/utils/helpers/__init__.py"

# Create __init__.py files in /opt/checkfiles
sudo touch "/opt/checkfiles/src/__init__.py"
sudo touch "/opt/checkfiles/src/validators/__init__.py"
sudo touch "/opt/checkfiles/src/validators/fastq/__init__.py"
sudo touch "/opt/checkfiles/src/utils/__init__.py"
sudo touch "/opt/checkfiles/src/utils/helpers/__init__.py"

# Create utils.py for common utility functions
echo "Creating utils module that validators depend on..."
cat > /opt/checkfiles/src/utils/__init__.py << 'EOF'
"""
Utility functions for Checkfiles.

This module provides common utility functions used by validator modules.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def get_file_extension(file_path: str) -> str:
    """Get the file extension from a path.
    
    Args:
        file_path: Path to file
        
    Returns:
        File extension (lowercase, without the dot)
    """
    _, ext = os.path.splitext(file_path)
    return ext.lower().lstrip('.')

def format_size(size_bytes: int) -> str:
    """Format a size in bytes to a human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable string (e.g., "1.23 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.2f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB"

def safe_open(file_path: str, mode: str = 'r') -> Optional[Any]:
    """Safely open a file with error handling.
    
    Args:
        file_path: Path to file
        mode: File open mode
        
    Returns:
        File object or None if error
    """
    try:
        return open(file_path, mode)
    except Exception as e:
        logger.error(f"Error opening file {file_path}: {e}")
        return None
EOF

# Create helpers module that validators depend on
echo "Creating helpers module that validators depend on..."
cat > /opt/checkfiles/src/utils/helpers/__init__.py << 'EOF'
"""
Helper utilities for Checkfiles.

This module provides additional helper functions used by validator modules.
"""

import os
import sys
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple, BinaryIO

logger = logging.getLogger(__name__)

def calculate_file_hashes(file_path: str) -> Dict[str, str]:
    """Calculate MD5 and SHA256 hashes for a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with hash values
    """
    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, 'rb') as f:
            # Read file in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b''):
                md5_hash.update(chunk)
                sha256_hash.update(chunk)
                
        return {
            'md5sum': md5_hash.hexdigest(),
            'sha256': sha256_hash.hexdigest()
        }
    except Exception as e:
        logger.error(f"Error calculating hashes for {file_path}: {e}")
        return {
            'md5sum': '',
            'sha256': ''
        }

def has_gz_extension(file_path: str) -> bool:
    """Check if a file has a gzip extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file has a gzip extension, False otherwise
    """
    extensions = ['.gz', '.gzip', '.bgz', '.bgzip']
    lower_path = file_path.lower()
    return any(lower_path.endswith(ext) for ext in extensions)

def is_gzipped(file_path: str) -> bool:
    """Check if a file is gzipped by examining its header.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is gzipped, False otherwise
    """
    try:
        with open(file_path, 'rb') as f:
            # Check for gzip magic number (1f 8b)
            return f.read(2) == b'\x1f\x8b'
    except Exception as e:
        logger.error(f"Error checking if {file_path} is gzipped: {e}")
        return False

def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get basic information about a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file information
    """
    try:
        file_stat = os.stat(file_path)
        return {
            'size': file_stat.st_size,
            'modified': file_stat.st_mtime,
            'exists': True,
            'is_gzipped': is_gzipped(file_path)
        }
    except Exception as e:
        logger.error(f"Error getting info for {file_path}: {e}")
        return {
            'size': 0,
            'modified': 0,
            'exists': False,
            'is_gzipped': False
        }

def setup_logging(level=logging.INFO):
    """Set up basic logging configuration.
    
    Args:
        level: Logging level
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
EOF

# Copy utils module to site-packages
sudo cp -f /opt/checkfiles/src/utils/__init__.py "${SITE_PACKAGES}/src/utils/__init__.py"
sudo cp -f /opt/checkfiles/src/utils/helpers/__init__.py "${SITE_PACKAGES}/src/utils/helpers/__init__.py"

# Install the package in development mode
echo "Installing package in development mode..."
cd /opt/checkfiles || { echo "ERROR: Cannot change to /opt/checkfiles directory"; exit 1; }

# Verify Python setup files exist
if [ ! -f setup.py ] && [ ! -f pyproject.toml ]; then
    echo "WARNING: Neither setup.py nor pyproject.toml found in /opt/checkfiles"
    echo "Creating a basic setup.py file..."
    cat > setup.py << 'EOF'
from setuptools import setup, find_packages

setup(
    name="checkfiles",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "crcmod>=1.7",
        "h5py>=3.0.0",
    ],
)
EOF
fi

# Install needed dependencies
echo "Installing Python dependencies..."
sudo pip3 install crcmod==1.7
sudo pip3 install -e .

# Create consistent import structure
echo "Creating consistent module structure..."

# Create base.py with BaseValidator class
echo "Creating base.py for BaseValidator..."
if [ ! -f "/opt/checkfiles/src/validators/base.py" ]; then
    cat > /opt/checkfiles/src/validators/base.py << 'EOF'
"""
Base validator implementation.

This module provides the BaseValidator class that other validators extend.
"""

import hashlib
import logging
import crcmod.predefined
from typing import Dict, Any, BinaryIO, Optional, Tuple

from src.utils import get_file_extension, format_size
from src.utils.helpers import calculate_file_hashes, is_gzipped, get_file_info

logger = logging.getLogger(__name__)

class HashCalculatingStream:
    """Stream wrapper that calculates hashes during reading."""
    
    def __init__(self, stream: BinaryIO):
        """Initialize the hash calculating stream.
        
        Args:
            stream: The input stream to wrap
        """
        self.stream = stream
        self.md5 = hashlib.md5()
        self.sha256 = hashlib.sha256()
        self.crc32c = crcmod.predefined.mkCrcFun('crc-32c')
        self.crc32c_value = 0
        self.position = 0
        self.size = 0
        
    def read(self, size=-1):
        """Read from the stream and update hashes.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Bytes read from stream
        """
        data = self.stream.read(size)
        if data:
            self.md5.update(data)
            self.sha256.update(data)
            self.crc32c_value = self.crc32c(data, self.crc32c_value)
            self.position += len(data)
            self.size += len(data)
        return data

class BaseValidator:
    """Base class for all file validators."""
    
    def __init__(self):
        """Initialize the base validator."""
        self.logger = logger
    
    def create_hash_calculating_stream(self, stream: BinaryIO, is_gzipped: bool = False) -> Tuple[BinaryIO, Dict[str, Any]]:
        """Create a stream that calculates hashes while reading.
        
        Args:
            stream: Input binary stream
            is_gzipped: Whether the stream is gzipped
            
        Returns:
            Tuple of (wrapped stream, metadata dict)
        """
        hash_stream = HashCalculatingStream(stream)
        metadata = {"is_gzipped": is_gzipped}
        return hash_stream, metadata
    
    def get_hash_values(self, hash_stream: HashCalculatingStream, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Get hash values from a hash calculating stream.
        
        Args:
            hash_stream: The hash calculating stream
            metadata: Stream metadata
            
        Returns:
            Dictionary with hash values
        """
        return {
            "md5sum": hash_stream.md5.hexdigest(),
            "sha256": hash_stream.sha256.hexdigest(),
            "crc32c": format(hash_stream.crc32c_value & 0xFFFFFFFF, '08x'),
            "size": hash_stream.size
        }
    
    def format_validation_result(self, valid: bool, errors: Optional[Dict[str, Any]] = None, 
                               warnings: Optional[Dict[str, Any]] = None, 
                               stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Format the validation result.
        
        Args:
            valid: Whether the file is valid
            errors: Any validation errors
            warnings: Any validation warnings
            stats: File statistics
            
        Returns:
            Formatted validation result
        """
        return {
            "valid": valid,
            "errors": errors or {},
            "warnings": warnings or {},
            "stats": stats or {}
        }
EOF
fi

# Create fastq.py that imports from fastq.validator
if [ ! -f "/opt/checkfiles/src/validators/fastq.py" ] || ! grep -q "from .fastq.validator import" "/opt/checkfiles/src/validators/fastq.py"; then
    cat > /opt/checkfiles/src/validators/fastq.py << 'EOF'
"""
FASTQ file and stream validator with pure Python implementation.

This module provides the FastqValidator class for validating FASTQ files 
and streams. Import and usage remains the same for backward compatibility,
but implementation has been refactored into separate modules.
"""

from .fastq.validator import FastqValidator

__all__ = ["FastqValidator"]
EOF
fi

# Create a standardized versions of these files in site-packages as well
echo "Synchronizing files between /opt/checkfiles and site-packages..."
sudo cp -f /opt/checkfiles/src/validators/base.py "${SITE_PACKAGES}/src/validators/base.py"
sudo cp -f /opt/checkfiles/src/validators/fastq.py "${SITE_PACKAGES}/src/validators/fastq.py"

# Copy all other validator files found in the source 
for file in $(find /opt/checkfiles/src/validators -type f -name "*.py" 2>/dev/null); do
    rel_path=${file#/opt/checkfiles/src/validators/}
    target_file="${SITE_PACKAGES}/src/validators/${rel_path}"
    sudo mkdir -p "$(dirname "$target_file")"
    sudo cp -f "$file" "$target_file"
    echo "Copied $file to $target_file"
done

# Ensure correct permissions
sudo chmod -R 777 "${SITE_PACKAGES}/src"
sudo chmod -R 777 "/opt/checkfiles/src"

# Create a symbolic link from old structure for backward compatibility
echo "Creating compatibility links for legacy imports..."
sudo mkdir -p "${SITE_PACKAGES}/validators"
sudo chmod 777 "${SITE_PACKAGES}/validators"
sudo touch "${SITE_PACKAGES}/validators/__init__.py"

# Link all validator modules for backward compatibility
for file in $(find "${SITE_PACKAGES}/src/validators" -maxdepth 1 -type f -name "*.py" 2>/dev/null); do
    base_name=$(basename "$file")
    if [ "$base_name" != "__init__.py" ]; then
        sudo ln -sf "$file" "${SITE_PACKAGES}/validators/${base_name}"
        echo "Created compatibility link for $base_name"
    fi
done

# Verify crcmod is installed
echo "Verifying crcmod installation..."
python3 -c "import crcmod; import crcmod.predefined; print('crcmod module imported successfully')" || {
    echo "ERROR: crcmod module not installed properly"
    echo "Trying to reinstall crcmod..."
    sudo pip3 install --force-reinstall crcmod
    python3 -c "import crcmod; import crcmod.predefined; print('crcmod module imported successfully')" || {
        echo "ERROR: Failed to install crcmod module"
        exit 1
    }
}

echo "Validator modules setup completed." 