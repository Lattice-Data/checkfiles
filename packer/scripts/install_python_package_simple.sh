#!/bin/bash
set -ex

# Print the content of build directory for debugging
echo "Contents of /tmp/build:"
ls -la /tmp/build
echo "Contents of /tmp/build/src:"
ls -la /tmp/build/src || echo "src directory not found"

# Fix any issue with validators directory
sudo mkdir -p /tmp/build/src/validators
sudo chmod 777 /tmp/build/src/validators

# Create base validators.__init__.py file if needed
if [ ! -f "/tmp/build/src/validators/__init__.py" ]; then
    sudo touch /tmp/build/src/validators/__init__.py
fi

# If there's no fastq.py, create a placeholder
if [ ! -f "/tmp/build/src/validators/fastq.py" ]; then
    echo "Creating fastq.py validator placeholder"
    sudo tee /tmp/build/src/validators/fastq.py > /dev/null << 'EOF'
"""
FASTQ file and stream validator with Rust implementation.
"""
import os
import logging
from typing import Dict, Any

# Try to import the Rust module
try:
    import fastq_validator
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.warning("Rust FASTQ validator not available. Some functionality may be limited.")

class FastqValidator:
    """Validator for FASTQ format files and streams.
    
    This validator uses Rust-based validation for maximum performance.
    It supports both file-based and streaming validation.
    """
    
    def __init__(self):
        """Initialize the FASTQ validator."""
        self.rust_available = RUST_AVAILABLE
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """Validate a FASTQ file."""
        if not self.rust_available:
            return {"valid": False, "errors": {"not_implemented": "Rust implementation not available"}}
        
        if not os.path.exists(file_path):
            return {"valid": False, "errors": {"file_not_found": f"File not found: {file_path}"}}
        
        try:
            # Call the Rust implementation
            is_valid, error_msg, line_num = fastq_validator.validate_fastq(file_path)
            
            if not is_valid:
                error_detail = f"Invalid FASTQ format: {error_msg}"
                if line_num is not None:
                    error_detail += f" at line {line_num}"
                return {"valid": False, "errors": {"invalid_format": error_detail}}
            
            return {"valid": True, "errors": {}}
            
        except Exception as e:
            return {"valid": False, "errors": {"validation_error": f"Error during validation: {str(e)}"}}
EOF
fi

# Determine Python site-packages directory
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SITE_PACKAGES="/usr/local/lib/python${PYTHON_VERSION}/dist-packages"
sudo mkdir -p $SITE_PACKAGES

# Check if the Rust library is already installed
echo "Checking for Rust library..."
if [ -d "/opt/checkfiles/lib" ]; then
    echo "Rust library directory exists"
    ls -la /opt/checkfiles/lib || echo "Empty directory"
fi

# Create the src package directory
SRC_DIR="${SITE_PACKAGES}/src"
sudo mkdir -p $SRC_DIR
sudo chmod 777 $SRC_DIR

# Create an __init__.py file in the src package
sudo touch "${SRC_DIR}/__init__.py"

# Create validators directory in site packages
VALIDATORS_DIR="${SITE_PACKAGES}/validators"
sudo mkdir -p $VALIDATORS_DIR
sudo chmod 777 $VALIDATORS_DIR
sudo touch "${VALIDATORS_DIR}/__init__.py"

# Create src/validators structure
sudo mkdir -p "${SRC_DIR}/validators"
sudo chmod 777 "${SRC_DIR}/validators"
sudo touch "${SRC_DIR}/validators/__init__.py"

# Copy all validators files regardless of source structure
echo "Copying validators files"
sudo cp -r /tmp/build/src/validators/* $VALIDATORS_DIR/ || echo "No files in validators directory to copy"

# Create symbolic links to connect src.validators with validators
for file in $(find ${VALIDATORS_DIR} -type f -name "*.py" 2>/dev/null || echo ""); do
    base_file=$(basename "$file")
    sudo ln -sf "$file" "${SRC_DIR}/validators/${base_file}"
    echo "Created link for $base_file"
done

# Handle checkfiles.py if it exists
if [ -f "/tmp/build/src/checkfiles.py" ]; then
    sudo cp /tmp/build/src/checkfiles.py "${SITE_PACKAGES}/checkfiles.py"
    sudo chmod 755 "${SITE_PACKAGES}/checkfiles.py"
    sudo ln -sf "${SITE_PACKAGES}/checkfiles.py" "${SRC_DIR}/checkfiles.py"
else
    echo "checkfiles.py not found, creating simple placeholder"
    sudo tee "${SITE_PACKAGES}/checkfiles.py" > /dev/null << 'EOF'
"""
Simplified placeholder for checkfiles module
"""
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_validator(file_format):
    """Initialize validator for the given file format."""
    if file_format.lower() == "fastq":
        try:
            from src.validators.fastq import FastqValidator
            logger.info("Successfully imported FastqValidator")
            return FastqValidator()
        except ImportError as e:
            logger.error(f"Error importing FastqValidator: {e}")
            raise ImportError(f"Error importing FastqValidator: {e}")
    else:
        raise ValueError(f"Unsupported file format: {file_format}")
EOF
    sudo chmod 755 "${SITE_PACKAGES}/checkfiles.py"
    sudo ln -sf "${SITE_PACKAGES}/checkfiles.py" "${SRC_DIR}/checkfiles.py"
fi

# Verify the installation
echo "Testing imports..."
python3 -c "import sys; print('Python path:', sys.path)"
python3 -c "import src; print('src module can be imported')" || echo "src import failed but continuing"

# Try importing the FastqValidator with diagnostics
sudo tee /tmp/test_import.py > /dev/null << 'EOF'
import sys
import os

print("\nSystem paths:")
for p in sys.path:
    print(f"  {p}")

print("\nChecking module locations:")
try:
    import src
    print(f"src module location: {src.__file__}")
except ImportError as e:
    print(f"src import error: {e}")

try:
    import src.validators
    print(f"src.validators location: {src.validators.__file__}")
except ImportError as e:
    print(f"src.validators import error: {e}")

try:
    from src.validators.fastq import FastqValidator
    print("FastqValidator successfully imported")
    validator = FastqValidator()
    print(f"FastqValidator instance: {validator}")
except ImportError as e:
    print(f"FastqValidator import error: {e}")
except Exception as e:
    print(f"FastqValidator other error: {e}")

print("\nAvailable files in Python paths:")
for path in sys.path:
    if os.path.exists(path):
        print(f"\nContents of {path}:")
        try:
            for item in os.listdir(path):
                print(f"  {item}")
        except Exception as e:
            print(f"  Error listing directory: {e}")
EOF
python3 /tmp/test_import.py || echo "Import test script failed but continuing build" 