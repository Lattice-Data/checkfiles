"""Tests for validator initialization logic.

This module tests that the correct validator is selected based on file format
and extension, particularly handling the case where HDF5 files with .h5ad extension
should use the H5adValidator.
"""

import pytest
import scanpy  # Import scanpy to ensure it's in sys.modules
from src.core.validation import initialize_validator

@pytest.mark.parametrize("file_format,file_path,expected_class", [
    ("fastq", "test.fastq", "FastqValidator"),
    ("fastq", "test.fastq.gz", "FastqValidator"),
    ("h5ad", "test.h5ad", "H5adValidator"),
    ("hdf5", "test.h5", "H5adValidator"),
    # The critical test case: hdf5 format with h5ad extension
    ("hdf5", "test.h5ad", "H5adValidator"),
])
def test_validator_selection(file_format, file_path, expected_class):
    """Test that the correct validator is selected based on format and extension."""
    validator = initialize_validator(file_format, file_path)
    assert validator.__class__.__name__ == expected_class, \
        f"Expected {expected_class} for format '{file_format}' and path '{file_path}', got {validator.__class__.__name__}" 