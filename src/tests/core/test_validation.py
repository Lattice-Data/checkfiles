"""
Unit tests for the validation module.
"""

import os
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock

from src.core.validation import initialize_validator

def test_initialize_validator_fastq():
    """Test initialization of a FastqValidator."""
    with patch('src.validators.fastq.FastqValidator') as mock_validator:
        # Set up the mock
        mock_validator.return_value = MagicMock()
        
        # Call the function
        validator = initialize_validator('fastq')
        
        # Check that the validator was created
        assert validator is not None

def test_initialize_validator_h5ad():
    """Test initialization of an H5adValidator."""
    with patch('src.validators.h5ad.H5adValidator') as mock_validator:
        # Set up the mock
        mock_validator.return_value = MagicMock()
        
        # Call the function
        validator = initialize_validator('h5ad')
        
        # Check that the validator was created
        assert validator is not None

def test_initialize_validator_unsupported():
    """Test initialization of an unsupported validator."""
    with pytest.raises(ValueError) as excinfo:
        initialize_validator('unsupported_format')
    
    assert 'Unsupported file format' in str(excinfo.value)

def test_initialize_validator_case_insensitive():
    """Test that validator initialization is case-insensitive."""
    with patch('src.validators.h5ad.H5adValidator') as mock_validator:
        # Set up the mock
        mock_validator.return_value = MagicMock()
        
        # Call the function with different cases
        validator1 = initialize_validator('H5AD')
        validator2 = initialize_validator('h5ad')
        
        # Check that the validator was created both times
        assert validator1 is not None
        assert validator2 is not None
        assert mock_validator.call_count == 2 