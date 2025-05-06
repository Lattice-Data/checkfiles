"""
Unit tests for the validation module.
"""

import os
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock, mock_open, Mock
import tempfile
import hashlib

from src.core.validation import (
    initialize_validator,
    validate_local_file,
    download_and_validate_random_access_file,
    calculate_hashes_for_stream,
    validate_s3_file,
    create_validation_record
)
from src.models.validation_record import FileValidationRecord
from src.tracking.progress import SimpleActivityTracker, ProgressTrackingStream

# Calculate actual MD5 for test data
TEST_FASTQ_CONTENT = b"@SEQ_ID\nGATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT\n+\n!''*((((***+))%%%++)(%%%%).1***-+*''))**55CCF>>>>>>CCCCCCC65"
TEST_FASTQ_MD5 = hashlib.md5(TEST_FASTQ_CONTENT).hexdigest()
TEST_FASTQ_SIZE = len(TEST_FASTQ_CONTENT)

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
    assert isinstance(result, FileValidationRecord)
    assert result.validation_success is True
    assert result.info['file_size'] == 1024
    assert result.info['md5sum'] == 'd41d8cd98f00b204e9800998ecf8427e'
    assert result.uuid == 'test_id'

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
    mock_init_validator.return_value = mock_validator_instance

    mock_calc_hashes.return_value = DUMMY_HASH_STATS_S3.copy()
    mock_download.return_value = ('/tmp/local_fake.h5ad', {'success': True}) # Simulate successful download

    # Call the function
    result = download_and_validate_random_access_file('s3://fake/path.h5ad', 'h5ad', identifier='s3_test_id')

    # Assertions
    mock_init_validator.assert_called_once_with('h5ad', 's3://fake/path.h5ad')
    mock_download.assert_called_once_with('s3://fake/path.h5ad', 'h5ad')
    mock_file_open.assert_any_call('/tmp/local_fake.h5ad', 'rb')
    mock_calc_hashes.assert_called_once()
    mock_validator_instance.validate_file.assert_called_once_with('/tmp/local_fake.h5ad')

    assert isinstance(result, FileValidationRecord)
    assert result.validation_success is True
    assert result.info['file_size'] == 2048
    assert result.info['md5sum'] == '999'
    assert result.uuid == 's3_test_id'
    mock_os_exists.assert_called_with('/tmp/local_fake.h5ad')
    mock_os_remove.assert_called_once_with('/tmp/local_fake.h5ad')

@pytest.fixture
def mock_validator():
    validator = Mock()
    # Mock validate_stream to handle the file content correctly
    validator.validate_stream.return_value = {
        'valid': True,
        'stats': {
            'file_size': TEST_FASTQ_SIZE,
            'md5sum': TEST_FASTQ_MD5,
            'sha256': 'test_sha256',
            'crc32c': 'test_crc32c'
        },
        'errors': {}
    }
    # Add a validate method that accepts a stream
    validator.validate = lambda stream, *args, **kwargs: validator.validate_stream.return_value
    return validator

@pytest.fixture
def mock_progress_tracker():
    tracker = Mock(spec=SimpleActivityTracker)
    # Add necessary methods
    tracker.init_file = Mock()
    tracker.complete_file = Mock()
    tracker.update_progress = Mock()
    return tracker

@pytest.fixture
def sample_file_content():
    return TEST_FASTQ_CONTENT

def test_create_validation_record():
    """Test creation of FileValidationRecord from validation results."""
    result = {
        'success': True,
        'results': {
            'valid': True,
            'stats': {
                'file_size': 1000,
                'md5sum': 'test_md5'
            },
            'errors': {}
        }
    }
    
    record = create_validation_record(result, 'test.txt', 'test-uuid', 'test-etag')
    
    assert isinstance(record, FileValidationRecord)
    assert record.file_path == 'test.txt'
    assert record.uuid == 'test-uuid'
    assert record.original_etag == 'test-etag'
    assert record.validation_success is True
    assert record.info['file_size'] == 1000
    assert record.info['md5sum'] == 'test_md5'
    assert not record.errors

def test_create_validation_record_with_error():
    """Test creation of FileValidationRecord with error information."""
    result = {
        'success': False,
        'error': 'Test error message'
    }
    
    record = create_validation_record(result, 'test.txt')
    
    assert isinstance(record, FileValidationRecord)
    assert record.validation_success is False
    assert record.errors['validation_error'] == 'Test error message'

@patch('src.core.validation.ProgressTrackingStream')
def test_validate_local_file_success(mock_tracking_stream, mock_validator, mock_progress_tracker, sample_file_content):
    """Test successful validation of a local file."""
    # Set up mock tracking stream
    mock_tracking_stream_instance = Mock(spec=ProgressTrackingStream)
    mock_tracking_stream.return_value = mock_tracking_stream_instance
    
    with tempfile.NamedTemporaryFile(suffix='.fastq', delete=False) as temp_file:
        temp_file.write(sample_file_content)
        temp_file.flush()
        
        record = validate_local_file(
            temp_file.name,
            'fastq',
            validator=mock_validator,
            progress_tracker=mock_progress_tracker
        )
        
        assert isinstance(record, FileValidationRecord)
        assert record.validation_success is True
        assert record.info['file_size'] == TEST_FASTQ_SIZE
        assert record.info['md5sum'] == TEST_FASTQ_MD5
        assert not record.errors
        
        mock_validator.validate_stream.assert_called_once()
        mock_progress_tracker.init_file.assert_called_once_with(temp_file.name)
        mock_progress_tracker.complete_file.assert_called_once()
        
        # Clean up
        try:
            os.unlink(temp_file.name)
        except:
            pass

def test_validate_local_file_not_found(mock_progress_tracker):
    """Test validation of non-existent local file."""
    record = validate_local_file(
        'nonexistent.fastq',
        'fastq',
        progress_tracker=mock_progress_tracker
    )
    
    assert isinstance(record, FileValidationRecord)
    assert record.validation_success is False
    assert record.errors['validation_error'] == 'File not found'

@patch('src.core.validation.stream_s3_file')
@patch('src.core.validation.ProgressTrackingStream')
def test_validate_s3_file_success(mock_tracking_stream, mock_stream_s3, mock_validator, mock_progress_tracker):
    """Test successful validation of an S3 file."""
    # Set up mock tracking stream
    mock_tracking_stream_instance = Mock(spec=ProgressTrackingStream)
    mock_tracking_stream.return_value = mock_tracking_stream_instance
    
    mock_stream = BytesIO(TEST_FASTQ_CONTENT)
    mock_stream_s3.return_value = mock_stream
    
    record = validate_s3_file(
        's3://test-bucket/test.fastq',
        'fastq',
        validator=mock_validator,
        progress_tracker=mock_progress_tracker
    )
    
    assert isinstance(record, FileValidationRecord)
    assert record.validation_success is True
    assert record.info['file_size'] == TEST_FASTQ_SIZE
    assert record.info['md5sum'] == TEST_FASTQ_MD5
    assert not record.errors
    
    mock_validator.validate_stream.assert_called_once()
    mock_progress_tracker.init_file.assert_called_once_with('s3://test-bucket/test.fastq')
    mock_progress_tracker.complete_file.assert_called_once()

@patch('src.core.validation.stream_s3_file')
def test_validate_s3_file_error(mock_stream_s3, mock_validator, mock_progress_tracker):
    """Test S3 file validation with error."""
    mock_stream_s3.side_effect = Exception("S3 access error")
    
    record = validate_s3_file(
        's3://test-bucket/test.fastq',
        'fastq',
        validator=mock_validator,
        progress_tracker=mock_progress_tracker
    )
    
    assert isinstance(record, FileValidationRecord)
    assert record.validation_success is False
    assert 'S3 access error' in record.errors['validation_error']

def test_calculate_hashes_for_stream():
    """Test hash calculation for a stream."""
    test_data = b"Test data for hash calculation"
    stream = BytesIO(test_data)
    
    stats = calculate_hashes_for_stream(stream, is_gzipped=False)
    
    assert 'file_size' in stats
    assert 'md5sum' in stats
    assert 'sha256' in stats
    assert 'crc32c' in stats
    assert stats['file_size'] == len(test_data)

def test_initialize_validator():
    """Test validator initialization."""
    with patch('src.validators.fastq.FastqValidator') as mock_validator_class:
        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        
        validator = initialize_validator('fastq', 'test.fastq')
        
        assert validator == mock_validator
        mock_validator_class.assert_called_once()

def test_initialize_validator_unsupported_format():
    """Test validator initialization with unsupported format."""
    with pytest.raises(ValueError, match="Unsupported file format"):
        initialize_validator('unsupported', 'test.txt') 