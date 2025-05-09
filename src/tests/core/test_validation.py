"""
Unit tests for the validation module.
"""

import os
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock, mock_open, Mock
import tempfile
import hashlib
import io
import gzip

from src.core.validation import (
    initialize_validator,
    validate_local_file,
    download_and_validate_random_access_file,
    calculate_hashes_for_stream,
    validate_s3_file,
    create_validation_record,
    track_validation_progress
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
    def validate_stream(stream, *args, **kwargs):
        # Read the stream to get actual size
        content = stream.read()
        return {
            'valid': True,
            'stats': {
                'file_size': len(content),
                'md5sum': 'test_md5',
                'sha256': 'test_sha256',
                'crc32c': 'test_crc32c'
            },
            'errors': {}
        }
    validator.validate_stream.side_effect = validate_stream
    return validator

@pytest.fixture
def mock_progress_tracker():
    tracker = Mock(spec=SimpleActivityTracker)
    # Add required methods with proper return values
    tracker.init_file.return_value = None
    tracker.update_progress.return_value = None
    tracker.complete_file.return_value = None
    return tracker

@pytest.fixture
def sample_file_content():
    return b"@SEQ_ID\nGATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT\n+\n!''*((((***+))%%%++)(%%%%).1***-+*''))**55CCF>>>>>>CCCCCCC65"

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

def test_validate_local_file_success(mock_validator, mock_progress_tracker, sample_file_content):
    """Test successful validation of a local file."""
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
        assert record.info['file_size'] == len(sample_file_content)
        assert record.info['md5sum'] == 'test_md5'
        assert not record.errors
        
        mock_validator.validate_stream.assert_called_once()
        mock_progress_tracker.init_file.assert_called_once_with(temp_file.name)
        mock_progress_tracker.complete_file.assert_called_once()

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

@patch('src.core.validation.calculate_hashes_for_stream')
@patch('src.core.validation.stream_s3_file')
def test_validate_s3_file_success(mock_stream_s3, mock_calculate_hashes, mock_validator, mock_progress_tracker):
    """Test successful validation of an S3 file."""
    sample_content = b"@SEQ_ID\nGATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT\n+\n!''*((((***+))%%%++)(%%%%).1***-+*''))**55CCF>>>>>>CCCCCCC65"
    
    class SeekableBytesIO(BytesIO):
        def __init__(self, initial_bytes):
            super().__init__(initial_bytes)
            self._closed = False
            
        def seekable(self):
            return True
            
        def readable(self):
            return True
            
        @property
        def closed(self):
            return self._closed
            
        def close(self):
            self._closed = True
            
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
    
    # Create two separate stream instances for hash calculation and validation
    hash_stream = SeekableBytesIO(sample_content)
    validation_stream = SeekableBytesIO(sample_content)
    
    # Mock stream_s3_file to return different streams for each call
    mock_stream_s3.side_effect = [hash_stream, validation_stream]
    
    # Mock hash calculation
    mock_calculate_hashes.return_value = {
        'file_size': len(sample_content),
        'md5sum': 'test_md5',
        'sha256': 'test_sha256',
        'crc32c': 'test_crc32c'
    }
    
    record = validate_s3_file(
        's3://test-bucket/test.fastq',
        'fastq',
        validator=mock_validator,
        progress_tracker=mock_progress_tracker
    )
    
    assert isinstance(record, FileValidationRecord)
    assert record.validation_success is True
    assert record.info['file_size'] == len(sample_content)
    assert record.info['md5sum'] == 'test_md5'
    assert not record.errors
    
    # Verify both streams were used
    assert mock_stream_s3.call_count == 2
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

def test_calculate_hashes_for_stream_regular():
    """Test hash calculation for regular (non-gzipped) data."""
    # Create test data
    test_data = b"This is some test data for hash calculation"
    input_stream = io.BytesIO(test_data)
    
    # Calculate expected hashes directly
    expected_md5 = hashlib.md5(test_data).hexdigest()
    expected_sha256 = hashlib.sha256(test_data).hexdigest()
    
    # Calculate hashes using the function
    hash_stats = calculate_hashes_for_stream(input_stream, is_gzipped=False)
    
    # Verify calculated hashes
    assert hash_stats['md5sum'] == expected_md5
    assert hash_stats['sha256'] == expected_sha256
    assert hash_stats['file_size'] == len(test_data)
    assert 'content_md5sum' not in hash_stats
    assert 'content_size' not in hash_stats

def test_calculate_hashes_for_stream_gzipped():
    """Test hash calculation for gzipped data."""
    # Create test data
    original_data = b"This is some test data that will be compressed"
    
    # Compress the data
    compressed_data = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_data, mode='wb') as gz:
        gz.write(original_data)
    
    # Get the compressed bytes and reset the stream
    compressed_bytes = compressed_data.getvalue()
    compressed_data.seek(0)
    
    # Calculate expected hashes directly
    expected_compressed_md5 = hashlib.md5(compressed_bytes).hexdigest()
    expected_compressed_sha256 = hashlib.sha256(compressed_bytes).hexdigest()
    expected_content_md5 = hashlib.md5(original_data).hexdigest()
    
    # Calculate hashes using the function
    hash_stats = calculate_hashes_for_stream(compressed_data, is_gzipped=True)
    
    # Verify calculated hashes
    assert hash_stats['md5sum'] == expected_compressed_md5
    assert hash_stats['sha256'] == expected_compressed_sha256
    assert hash_stats['file_size'] == len(compressed_bytes)
    assert hash_stats['content_md5sum'] == expected_content_md5
    assert hash_stats['content_size'] == len(original_data)

def test_calculate_hashes_for_stream_empty():
    """Test hash calculation for empty data."""
    input_stream = io.BytesIO(b"")
    
    hash_stats = calculate_hashes_for_stream(input_stream, is_gzipped=False)
    
    assert hash_stats['file_size'] == 0
    assert hash_stats['md5sum'] == hashlib.md5(b"").hexdigest()
    assert hash_stats['sha256'] == hashlib.sha256(b"").hexdigest()

def test_create_validation_record_basic():
    """Test creating a validation record with basic data."""
    result = {
        'valid': True,
        'stats': {'file_size': 1000},
        'errors': {}
    }
    
    record = create_validation_record(result, "test.h5ad")
    
    assert isinstance(record, FileValidationRecord)
    assert record.validation_success is True
    assert record.info['file_size'] == 1000
    assert not record.errors

def test_create_validation_record_with_errors():
    """Test creating a validation record with errors."""
    result = {
        'valid': False,
        'stats': {'file_size': 1000},
        'errors': {'format': 'Invalid format'}
    }
    
    record = create_validation_record(result, "test.h5ad")
    
    assert isinstance(record, FileValidationRecord)
    assert record.validation_success is False
    assert record.info['file_size'] == 1000
    assert record.errors['format'] == 'Invalid format'

def test_create_validation_record_with_uuid_and_etag():
    """Test creating a validation record with UUID and ETag."""
    result = {
        'valid': True,
        'stats': {'file_size': 1000},
        'errors': {}
    }
    
    uuid = "test-uuid"
    etag = "test-etag"
    
    record = create_validation_record(result, "test.h5ad", uuid=uuid, etag=etag)
    
    assert isinstance(record, FileValidationRecord)
    assert record.uuid == uuid
    assert record.original_etag == etag

def test_track_validation_progress():
    """Test progress tracking functionality."""
    mock_tracker = MagicMock(spec=SimpleActivityTracker)
    file_path = "test.h5ad"
    
    # Test status update
    track_validation_progress(file_path, mock_tracker, "Testing")
    mock_tracker.update_progress.assert_called_with(file_path, status="Testing")
    
    # Test completion
    results = {'valid': True, 'stats': {'file_size': 1000}}
    track_validation_progress(file_path, mock_tracker, "Complete", True, results)
    mock_tracker.complete_file.assert_called_with(file_path, True, results)

def test_track_validation_progress_no_tracker():
    """Test progress tracking with no tracker."""
    # Should not raise any errors
    track_validation_progress("test.h5ad", None, "Testing")
    track_validation_progress("test.h5ad", None, "Complete", True, {})

def test_initialize_validator_fastq():
    """Test initializing FastqValidator."""
    with patch('src.validators.fastq.FastqValidator') as mock_validator:
        mock_validator.return_value = MagicMock()
        validator = initialize_validator("fastq", "test.fastq.gz")
        assert isinstance(validator, MagicMock)

def test_initialize_validator_h5ad():
    """Test initializing H5adValidator."""
    with patch('src.validators.h5ad.H5adValidator') as mock_validator:
        mock_validator.return_value = MagicMock()
        validator = initialize_validator("h5ad", "test.h5ad")
        assert isinstance(validator, MagicMock)

def test_initialize_validator_invalid_format():
    """Test initializing validator with invalid format."""
    with pytest.raises(ValueError):
        initialize_validator("invalid_format", "test.txt")

def test_initialize_validator_import_error():
    """Test handling of import errors during validator initialization."""
    with patch('src.validators.fastq.FastqValidator', side_effect=ImportError("Test error")), \
         patch('validators.fastq.FastqValidator', side_effect=ImportError("Test error")), \
         patch('sys.path', []):  # Replace sys.path with an empty list
        with pytest.raises(ImportError, match="Error importing FastqValidator from all paths: Test error, Test error"):
            initialize_validator("fastq", "test.fastq.gz") 