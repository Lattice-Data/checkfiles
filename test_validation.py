#!/usr/bin/env python3
"""
Test script for validator initialization logic.

This script tests that the correct validator is selected based on file format
and extension, particularly handling the case where HDF5 files with .h5ad extension
should use the H5adValidator.
"""

import os
import sys
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# Import the validation functions
from src.core.validation import initialize_validator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_validator_selection():
    """Test that the correct validator is selected based on format and extension."""
    
    # Test cases with expected validator types
    test_cases = [
        # format, path, expected validator class name
        ("fastq", "test.fastq", "FastqValidator"),
        ("fastq", "test.fastq.gz", "FastqValidator"),
        ("h5ad", "test.h5ad", "H5adValidator"),
        ("hdf5", "test.hdf5", "Hdf5Validator"),
        ("hdf5", "test.h5", "Hdf5Validator"),
        # The critical test case: hdf5 format with h5ad extension
        ("hdf5", "test.h5ad", "H5adValidator"),
    ]
    
    # Run test cases
    for file_format, file_path, expected_class in test_cases:
        try:
            validator = initialize_validator(file_format, file_path)
            actual_class = validator.__class__.__name__
            
            if actual_class == expected_class:
                logger.info(f"✓ Format '{file_format}', path '{file_path}' -> {actual_class} (CORRECT)")
            else:
                logger.error(f"✗ Format '{file_format}', path '{file_path}' -> {actual_class}, expected {expected_class}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating format '{file_format}': {str(e)}")
            return False
            
    return True

if __name__ == "__main__":
    print("Testing validator selection logic...")
    success = test_validator_selection()
    
    if success:
        print("All tests passed successfully!")
        sys.exit(0)
    else:
        print("Tests failed.")
        sys.exit(1) 