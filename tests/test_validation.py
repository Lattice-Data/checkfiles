import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from src.core.validation import (
    validate_local_file,
    validate_s3_file,
    create_validation_record,
    initialize_validator,
    calculate_hashes_for_stream
)
from src.models.validation_record import FileValidationRecord
from src.tracking.progress import SimpleActivityTracker

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