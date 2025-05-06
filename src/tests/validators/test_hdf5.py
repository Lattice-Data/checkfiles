"""Tests for the Hdf5Validator."""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure h5py is importable for creating test files, or handle its absence
try:
    import h5py
except ImportError:
    h5py = None # Tests requiring actual h5py will be skipped

# Make src modules importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.validators.hdf5 import Hdf5Validator

# --- Fixtures --- 

@pytest.fixture
def validator():
    """Provides an instance of Hdf5Validator."""
    if h5py is None:
        pytest.skip("h5py not installed, skipping Hdf5Validator tests")
    return Hdf5Validator()

@pytest.fixture
def valid_h5_file(tmp_path):
    """Creates a minimal valid HDF5 file in a temporary directory."""
    if h5py is None:
        pytest.skip("h5py not installed, cannot create valid HDF5 test file")
    file_path = tmp_path / "valid.h5"
    with h5py.File(file_path, 'w') as f:
        f.create_dataset("data", data=[1, 2, 3])
    return str(file_path)

@pytest.fixture
def invalid_format_file(tmp_path):
    """Creates a text file that is not an HDF5 file."""
    file_path = tmp_path / "invalid.txt"
    file_path.write_text("This is not HDF5 content.")
    return str(file_path)

# --- Test Cases --- 

@pytest.mark.skipif(h5py is None, reason="h5py not installed")
def test_init_success():
    """Test successful initialization when h5py is present."""
    # If h5py wasn't installed, the fixture would skip this test
    validator_instance = Hdf5Validator()
    assert isinstance(validator_instance, Hdf5Validator)

def test_init_fail_no_h5py():
    """Test initialization fails if h5py is not importable."""
    # Temporarily pretend h5py is not imported within the validator module
    with patch('src.validators.hdf5.h5py', None):
        with pytest.raises(ImportError, match="h5py library is required"):
            Hdf5Validator()

def test_validate_valid_h5_file(validator, valid_h5_file):
    """Test validation passes for a structurally valid HDF5 file."""
    result = validator.validate_file(valid_h5_file)
    print(f"Validation Result (valid file): {result}") # Debug print
    assert result['valid'] is True
    assert not result['errors']
    assert result['stats']['is_hdf5_file'] is True
    assert result['stats']['hdf5_can_open'] is True
    # Check if hashes were calculated (values depend on exact file content)
    assert 'md5sum' in result['stats']
    assert 'sha256' in result['stats']

def test_validate_invalid_format_file(validator, invalid_format_file):
    """Test validation fails for a file that is not an HDF5 container."""
    result = validator.validate_file(invalid_format_file)
    print(f"Validation Result (invalid format): {result}") # Debug print
    assert result['valid'] is False
    assert "hdf5_format" in result['errors']
    assert result['stats']['is_hdf5_file'] is False
    assert 'hdf5_can_open' not in result['stats'] # Shouldn't try to open if not HDF5
    # Hashes should still be calculated if possible
    assert 'md5sum' in result['stats']

def test_validate_non_existent_file(validator, tmp_path):
    """Test validation fails gracefully for a non-existent file."""
    non_existent_path = str(tmp_path / "not_real.h5")
    result = validator.validate_file(non_existent_path)
    print(f"Validation Result (non-existent): {result}") # Debug print
    assert result['valid'] is False
    assert "file_access" in result['errors']
    assert not result['stats'] # No stats should be generated

@patch.object(Hdf5Validator, 'calculate_hashes')
def test_validate_hashing_error(mock_calc_hashes, validator, valid_h5_file):
    """Test validation handles errors during hash calculation."""
    mock_calc_hashes.side_effect = Exception("Hashing failed!")
    result = validator.validate_file(valid_h5_file)
    print(f"Validation Result (hash error): {result}") # Debug print
    # File is still valid HDF5, but should have a warning
    assert result['valid'] is True 
    assert not result['errors']
    assert "hash_calculation" in result['warnings']
    assert "Hashing failed!" in result['warnings']["hash_calculation"]
    assert result['stats']['is_hdf5_file'] is True
    assert result['stats']['hdf5_can_open'] is True
    # Hashes should be missing from stats
    assert 'md5sum' not in result['stats']

@patch('src.validators.hdf5.h5py.is_hdf5')
def test_validate_unexpected_error(mock_is_hdf5, validator, valid_h5_file):
    """Test validation handles unexpected errors during checks."""
    mock_is_hdf5.side_effect = Exception("Unexpected h5py error!")
    result = validator.validate_file(valid_h5_file)
    print(f"Validation Result (unexpected error): {result}") # Debug print
    assert result['valid'] is False 
    assert "unexpected_error" in result['errors']
    assert "Unexpected h5py error!" in result['errors']["unexpected_error"]
    # Stats might be partially populated before the error
    # Hashes should still be calculated because they happen before the mocked error point in this test
    assert 'md5sum' in result['stats'] 
 