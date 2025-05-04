"""
Tests for the HDF5 validator.

This module contains test cases for validating HDF5 files using the Hdf5Validator.
Tests cover validation of file formats, error conditions, and statistics collection.
"""
import os
import pytest
import tempfile
import io
import h5py
import numpy as np
from pathlib import Path

from src.validators.hdf5 import Hdf5Validator

@pytest.fixture
def validator():
    """
    Create an HDF5 validator instance for testing.
    
    Returns:
        Hdf5Validator: An initialized HDF5 validator
    """
    return Hdf5Validator()


@pytest.fixture
def test_hdf5_file():
    """
    Create a temporary HDF5 file for testing.
    
    Returns:
        str: Path to the temporary HDF5 file
    """
    # Skip if h5py is not available
    try:
        import h5py
    except ImportError:
        pytest.skip("h5py not installed, skipping HDF5 tests")
    
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as temp_file:
        temp_path = temp_file.name
    
    # Create a simple HDF5 file with some test data
    with h5py.File(temp_path, 'w') as f:
        # Create a group
        grp = f.create_group("test_group")
        
        # Create datasets
        f.create_dataset("dataset1", data=np.arange(10))
        grp.create_dataset("nested_dataset", data=np.random.rand(5, 5))
        
        # Add attributes
        f.attrs["file_attribute"] = "test"
        grp.attrs["group_attribute"] = 42
    
    yield temp_path
    
    # Clean up the test file
    try:
        os.unlink(temp_path)
    except:
        pass


def test_validate_file_valid(validator, test_hdf5_file):
    """Test validating a valid HDF5 file."""
    result = validator.validate_file(test_hdf5_file)
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0
    
    # Verify statistics
    stats = result["stats"]
    assert stats["groups"] > 0  # Should be at least 1 group (test_group)
    assert stats["datasets"] > 0  # Should be at least 2 datasets
    assert stats["attributes"] > 0  # Should be at least 2 attributes


def test_validate_file_not_found(validator):
    """Test validating a non-existent file."""
    result = validator.validate_file("/path/to/nonexistent/file.h5")
    
    assert result["valid"] is False
    assert "file_not_found" in result["errors"]


def test_validate_empty_file(validator):
    """Test validating an empty HDF5 file."""
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # Don't write anything to the file
        
        result = validator.validate_file(temp_path)
        
        assert result["valid"] is False
        # The error now comes from h5py trying to read the empty file stream
        assert "validation_error" in result["errors"], "Expected validation error for empty file"
        assert "file signature not found" in result["errors"]["validation_error"], "Expected specific h5py error for empty file"
    finally:
        # Clean up
        try:
            os.unlink(temp_path)
        except:
            pass


def test_validate_invalid_file(validator):
    """Test validating an invalid HDF5 file."""
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as temp_file:
        temp_path = temp_file.name
        
        # Write some random data that is not a valid HDF5 file
        temp_file.write(b"This is not a valid HDF5 file")
    
    try:
        result = validator.validate_file(temp_path)
        
        assert result["valid"] is False
        # Updated error message check for new format
        assert "validation_error" in result["errors"]
        assert "Invalid HDF5 structure" in result["errors"]["validation_error"] 
        assert "file signature not found" in result["errors"]["validation_error"] # More specific h5py error
    finally:
        # Clean up
        try:
            os.unlink(temp_path)
        except:
            pass


def test_validate_stream(validator):
    """Test validating an HDF5 stream."""
    # Create a test stream with invalid HDF5 data
    stream = io.BytesIO(b"Test data")
    
    result = validator.validate_stream(stream)
    
    assert result["valid"] is False
    assert "validation_error" in result["errors"]
    # Check the specific error message from h5py for invalid stream/signature
    # The error message format has changed in our recent updates
    error_message = result["errors"]["validation_error"]
    assert "Invalid HDF5 structure" in error_message
    assert "file signature not found" in error_message
    
    # Hashes are no longer calculated here
    # assert "file_size" in result["stats"] # No longer calculated here