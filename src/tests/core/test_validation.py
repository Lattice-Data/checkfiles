"""
Unit tests for the validation module.
"""

import os
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock, mock_open

from src.core.validation import initialize_validator, validate_local_file, download_and_validate_random_access_file, calculate_hashes_for_stream

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
    # Patch H5adValidator where it is imported and looked up in the module under test
    with patch('src.core.validation.H5adValidator') as mock_validator:
        # Set up the mock instance that the class call will return
        mock_instance = MagicMock()
        mock_validator.return_value = mock_instance
        # Set the __name__ attribute on the mock *class* itself for logging
        mock_validator.__name__ = 'H5adValidator' 
        
        # Call the function with different cases
        validator1 = initialize_validator('H5AD')
        validator2 = initialize_validator('h5ad')
        
        # Check that the validator instances were returned
        assert validator1 is mock_instance
        assert validator2 is mock_instance
        # Check that the mock class was called twice to create the instances
        assert mock_validator.call_count == 2

# Dummy H5AD stats for mocking
DUMMY_H5AD_STATS = {
    'observation_count': 100,
    'variable_count': 2000,
    'feature_counts': [{'feature_type': 'gene', 'feature_count': 2000}],
    'genomes': ['GRCh38'],
    'is_hdf5': True
}

# Dummy hash values for mocking
DUMMY_HASH_STATS_LOCAL = {'md5sum': 'd41d8cd98f00b204e9800998ecf8427e', 'file_size': 1024, 'sha256': 'abc', 'crc32c': '123'}
DUMMY_HASH_STATS_S3 = {'sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'file_size': 2048, 'md5sum': '999', 'crc32c': '456'}

@patch('src.core.validation.calculate_hashes_for_stream')
@patch('src.core.validation.initialize_validator')
@patch('builtins.open', new_callable=mock_open) # Mock open for local file reading
@patch('os.path.exists', return_value=True) # Assume file exists
def test_validate_local_h5ad_calculates_hashes(mock_os_exists, mock_file_open, mock_init_validator, mock_calc_hashes):
    """Verify local H5AD validation calculates and merges hashes."""
    # Setup mocks
    mock_validator_instance = MagicMock() # spec=H5adValidator removed for simplicity if class not imported
    mock_validator_instance.validate_file.return_value = {'valid': True, 'errors': {}, 'stats': DUMMY_H5AD_STATS.copy()}
    mock_init_validator.return_value = mock_validator_instance
    mock_calc_hashes.return_value = DUMMY_HASH_STATS_LOCAL.copy()

    # Call the function
    result = validate_local_file('/fake/path.h5ad', 'h5ad', identifier='test_id')

    # Assertions
    mock_init_validator.assert_called_once_with('h5ad', '/fake/path.h5ad')
    mock_file_open.assert_called_once_with('/fake/path.h5ad', 'rb') # Check open called for hash calc
    mock_calc_hashes.assert_called_once() # Check hash calc was called
    mock_validator_instance.validate_file.assert_called_once_with('/fake/path.h5ad')
    assert result['success'] is True
    assert 'results' in result
    assert 'stats' in result['results']
    # Check merged stats
    expected_stats = {**DUMMY_H5AD_STATS, **DUMMY_HASH_STATS_LOCAL}
    assert result['results']['stats'] == expected_stats
    assert result['identifier'] == 'test_id'

@patch('src.core.validation.download_s3_file_to_scratch')
@patch('src.core.validation.calculate_hashes_for_stream')
@patch('src.core.validation.initialize_validator')
@patch('os.remove')
@patch('os.path.exists', return_value=True) # Mock os.path.exists for cleanup check
@patch('builtins.open', new_callable=mock_open) # Mock open for hash calculation on downloaded file
def test_download_validate_h5ad_calls_validate_file_and_merges_hashes(mock_file_open, mock_os_exists, mock_os_remove, mock_init_validator, mock_calc_hashes, mock_download):
    """Verify S3 H5AD validation downloads, calls validate_file, merges hashes."""
    # Setup mocks
    mock_validator_instance = MagicMock() # spec=H5adValidator removed
    # IMPORTANT: Mock validate_file, not validate_stream
    mock_validator_instance.validate_file.return_value = {'valid': True, 'errors': {}, 'stats': DUMMY_H5AD_STATS.copy()}
    # Add validate_stream to the mock spec if we want to assert it's NOT called
    # mock_validator_instance.validate_stream = MagicMock()
    mock_init_validator.return_value = mock_validator_instance

    mock_calc_hashes.return_value = DUMMY_HASH_STATS_S3.copy()
    mock_download.return_value = ('/tmp/local_fake.h5ad', {'success': True}) # Simulate successful download

    # Call the function
    result = download_and_validate_random_access_file('s3://fake/path.h5ad', 'h5ad', identifier='s3_test_id')

    # Assertions
    mock_init_validator.assert_called_once_with('h5ad', 's3://fake/path.h5ad')
    mock_download.assert_called_once_with('s3://fake/path.h5ad', 'h5ad')
    # Check open called for hash calc - use assert_any_call as mocks might open internally
    mock_file_open.assert_any_call('/tmp/local_fake.h5ad', 'rb')
    mock_calc_hashes.assert_called_once() # Check hash calc called
    mock_validator_instance.validate_file.assert_called_once_with('/tmp/local_fake.h5ad')
    # Ensure validate_stream was NOT called (optional but good practice)
    # mock_validator_instance.validate_stream.assert_not_called()

    assert result['success'] is True # Should reflect validator's 'valid' status
    assert 'results' in result
    assert 'stats' in result['results']
    # Check merged stats
    expected_stats = {**DUMMY_H5AD_STATS, **DUMMY_HASH_STATS_S3}
    assert result['results']['stats'] == expected_stats
    assert result['identifier'] == 's3_test_id'
    # Check cleanup
    # os.path.exists needs to be called twice: once for the check before remove, once potentially inside download
    mock_os_exists.assert_called_with('/tmp/local_fake.h5ad')
    mock_os_remove.assert_called_once_with('/tmp/local_fake.h5ad')

# Consider adding tests for failure cases:
# - Hash calculation fails for local H5AD
# - Download fails for S3 H5AD
# - validate_file throws an exception

# ... existing tests ... 