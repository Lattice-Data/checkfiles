#!/bin/bash
set -euo pipefail

echo "Validator modules setup script for Checkfiles."
echo ""
echo "This script sets up the validator modules by:"
echo "1. Installing the Python package in development mode"
echo "2. Creating necessary directories"
echo "3. Creating validator stubs"
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
SITE_PACKAGES="/usr/local/lib/python${PYTHON_VERSION}/dist-packages"

# Create necessary directories in site-packages
echo "Setting up package directories in site-packages..."
sudo mkdir -p "${SITE_PACKAGES}/src"
sudo mkdir -p "${SITE_PACKAGES}/src/validators"
sudo mkdir -p "${SITE_PACKAGES}/src/validators/fastq"
sudo chmod -R 777 "${SITE_PACKAGES}/src"

# Create necessary directories in /opt/checkfiles
echo "Setting up package directories in /opt/checkfiles..."
sudo mkdir -p "/opt/checkfiles/src/validators"
sudo mkdir -p "/opt/checkfiles/src/validators/fastq"
sudo chmod -R 777 "/opt/checkfiles/src"

# Create __init__.py files in site-packages
sudo touch "${SITE_PACKAGES}/src/__init__.py"
sudo touch "${SITE_PACKAGES}/src/validators/__init__.py"
sudo touch "${SITE_PACKAGES}/src/validators/fastq/__init__.py"

# Create __init__.py files in /opt/checkfiles
sudo touch "/opt/checkfiles/src/__init__.py"
sudo touch "/opt/checkfiles/src/validators/__init__.py"
sudo touch "/opt/checkfiles/src/validators/fastq/__init__.py"

# Install the package in development mode
echo "Installing package in development mode..."
cd /opt/checkfiles || { echo "ERROR: Cannot change to /opt/checkfiles directory"; exit 1; }

# Verify Python setup files exist
if [ ! -f setup.py ] && [ ! -f pyproject.toml ]; then
    echo "ERROR: Neither setup.py nor pyproject.toml found in /opt/checkfiles"
    exit 1
fi

# Install crcmod dependency
echo "Installing additional Python dependencies..."
sudo pip3 install crcmod==1.7

sudo pip3 install -e .

# Create proper imports in fastq.py
echo "Creating fastq.py for proper imports..."
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

# Create base.py for the BaseValidator class
echo "Creating base.py for BaseValidator..."
cat > /opt/checkfiles/src/validators/base.py << 'EOF'
"""
Base validator implementation.

This module provides the BaseValidator class that other validators extend.
"""

import hashlib
import logging
import crcmod.predefined
from typing import Dict, Any, BinaryIO, Optional, Tuple

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

# Copy files to site-packages
echo "Copying files to site-packages..."
sudo cp /opt/checkfiles/src/validators/fastq.py "${SITE_PACKAGES}/src/validators/fastq.py"
sudo cp /opt/checkfiles/src/validators/base.py "${SITE_PACKAGES}/src/validators/base.py"

# Ensure correct permissions
sudo chmod -R 777 "${SITE_PACKAGES}/src"
sudo chmod -R 777 "/opt/checkfiles/src"

# Verify crcmod is installed
echo "Verifying crcmod installation..."
python3 -c "import crcmod; print(f'crcmod version: {crcmod.__version__}')" || {
    echo "ERROR: crcmod module not installed properly"
    echo "Trying to reinstall crcmod..."
    sudo pip3 install --force-reinstall crcmod
    python3 -c "import crcmod; print(f'crcmod version: {crcmod.__version__}')" || {
        echo "ERROR: Failed to install crcmod module"
        exit 1
    }
}

# Verify installation by trying to import from src.validators
echo "Verifying installation..."
python3 -c "from src.validators.base import BaseValidator; print('BaseValidator imported successfully')" || {
    echo "ERROR: Failed to import BaseValidator"
    exit 1
}

python3 -c "from src.validators.fastq import FastqValidator; print('FastqValidator imported successfully')" || {
    echo "ERROR: Failed to import FastqValidator from src.validators.fastq"
    echo "This is critical for the operation of the checkfiles software."
    exit 1
}

# Create a test script that verifies the validator works
echo "Creating test script..."
cat > /tmp/test_validator.py << 'EOF'
#!/usr/bin/env python3
"""
Test script for verifying the validator functionality.
"""

import io
import sys
from src.validators.fastq import FastqValidator

def test_validator():
    """Test that the validator can be instantiated and methods work."""
    try:
        # Create validator
        validator = FastqValidator()
        print("✓ FastqValidator instantiated successfully")
        
        # Check methods
        assert hasattr(validator, 'validate_file'), "Missing validate_file method"
        assert hasattr(validator, 'validate_stream'), "Missing validate_stream method"
        print("✓ FastqValidator has required methods")
        
        # Test validate_stream with a simple FASTQ
        test_data = b"""@SEQ_ID
GATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT
+
!''*((((***+))%%%++)(%%%%).1***-+*''))**55CCF>>>>>>CCCCCCC65
"""
        stream = io.BytesIO(test_data)
        result = validator.validate_stream(stream)
        assert result['valid'], "Validation failed"
        assert 'stats' in result, "Missing stats in result"
        print("✓ validate_stream works correctly")
        
        print("\nAll tests passed!")
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_validator()
    sys.exit(0 if success else 1)
EOF

# Run the test script
echo "Running validator test..."
python3 /tmp/test_validator.py || {
    echo "ERROR: Validator test failed"
    exit 1
}

# Run tests only if tests directory exists
echo "Running tests..."
if [ -d "tests" ]; then
    cd /opt/checkfiles || exit 1
    python3 -m pytest tests/
else
    echo "NOTICE: No tests directory found, skipping tests"
fi

echo "Validator modules setup completed." 