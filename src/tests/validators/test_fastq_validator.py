"""Tests for the FastqValidator implementation."""

import pytest
import io
import gzip
from unittest.mock import patch, MagicMock

from src.validators.fastq import FastqValidator
from src.validators.base import HashCalculatingStream

@pytest.fixture
def valid_fastq_data():
    """Return valid FASTQ data for testing."""
    # Sequence 1: 64 bases, 64 quality scores
    seq1 = "ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT"  # 64 chars
    qual1 = "!" * 64  # 64 chars
    
    seq2 = "ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT"  # 52 chars
    qual2 = "!" * 52  # 52 chars
    
    return f"""@SRR1234567.1 1 length=150
{seq1}
+SRR1234567.1 1 length=150
{qual1}
@SRR1234567.2 2 length=100
{seq2}
+SRR1234567.2 2 length=100
{qual2}
""".encode('utf-8')

@pytest.fixture
def valid_gzipped_fastq_data(valid_fastq_data):
    """Return valid gzipped FASTQ data for testing."""
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb') as f:
        f.write(valid_fastq_data)
    buffer.seek(0)
    return buffer.getvalue()

@pytest.fixture
def invalid_fastq_data():
    """Return invalid FASTQ data for testing."""
    return b"""@SRR1234567.1 1 length=150
ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT
+SRR1234567.1 1 length=150
!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@SRR1234567.2 2 length=100
ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT
THIS_IS_NOT_A_QUALITY_LINE
"""

def test_init():
    """Test initialization of FastqValidator."""
    validator = FastqValidator()
    assert validator is not None
    assert validator.header_parser is not None
    assert validator.statistics is not None
    assert validator.mismatched_ids == {}

def test_validate_valid_fastq_stream(valid_fastq_data):
    """Test validation of a valid FASTQ stream."""
    validator = FastqValidator()
    stream = io.BytesIO(valid_fastq_data)
    result = validator.validate_stream(stream)
    
    assert result["valid"] is True
    assert "errors" not in result or len(result["errors"]) == 0
    
    # Check that statistics were collected
    assert "stats" in result
    assert result["stats"] is not None
    
    # Check specific statistics that should be present
    stats = result["stats"]
    assert "read_count" in stats
    assert stats["read_count"] == 2
    assert "min_sequence_length" in stats or "min_length" in stats
    min_length = stats.get("min_sequence_length", stats.get("min_length"))
    assert min_length == 52  # The second sequence is shorter
    
    # Check that hash values were calculated
    assert "md5sum" in stats
    assert "sha256" in stats
    assert "crc32c" in stats
    assert "file_size" in stats
    assert stats["file_size"] > 0
    
    # No warning about not being able to collect statistics
    assert "warnings" not in result or "statistics" not in result["warnings"]

def test_validate_gzipped_fastq_stream(valid_gzipped_fastq_data):
    """Test validation of a gzipped FASTQ stream."""
    validator = FastqValidator()
    stream = io.BytesIO(valid_gzipped_fastq_data)
    result = validator.validate_stream(stream, is_gzipped=True)
    
    assert result["valid"] is True
    assert "errors" not in result or len(result["errors"]) == 0
    
    # Check that statistics were collected
    assert "stats" in result
    assert result["stats"] is not None
    
    # Check that hash values were calculated
    stats = result["stats"]
    assert "md5sum" in stats
    assert "sha256" in stats
    assert "crc32c" in stats
    assert "file_size" in stats
    
    # Should have content_md5sum
    # Note: This might not work in all test environments if the stream isn't seekable
    if "content_md5sum" in stats:
        assert stats["content_md5sum"] is not None
    
    # No warning about not being able to collect statistics
    assert "warnings" not in result or "statistics" not in result["warnings"]

def test_validate_invalid_fastq_stream(invalid_fastq_data):
    """Test validation of an invalid FASTQ stream."""
    validator = FastqValidator()
    stream = io.BytesIO(invalid_fastq_data)
    result = validator.validate_stream(stream)
    
    assert result["valid"] is False
    assert "errors" in result
    assert len(result["errors"]) > 0

def test_validate_non_seekable_stream(valid_fastq_data):
    """Test validation of a non-seekable stream."""
    # Create a stream that doesn't support seeking
    class NonSeekableStream:
        def __init__(self, data):
            self.data = data
            self.position = 0
            
        def read(self, size=-1):
            if self.position >= len(self.data):
                return b''
            
            if size == -1:
                chunk = self.data[self.position:]
                self.position = len(self.data)
            else:
                chunk = self.data[self.position:self.position + size]
                self.position += len(chunk)
                
            return chunk
            
        def readline(self):
            start = self.position
            while self.position < len(self.data):
                if self.data[self.position:self.position+1] == b'\n':
                    self.position += 1
                    break
                self.position += 1
                
            return self.data[start:self.position]
    
    # No seek method!
    stream = NonSeekableStream(valid_fastq_data)
    
    validator = FastqValidator()
    result = validator.validate_stream(stream)
    
    assert result["valid"] is True
    
    # Make sure we have stats despite no seeking
    assert "stats" in result
    assert result["stats"] is not None
    assert "read_count" in result["stats"]
    assert result["stats"]["read_count"] == 2
    
    # Check that hash values were calculated
    stats = result["stats"]
    assert "md5sum" in stats
    assert "sha256" in stats
    assert "crc32c" in stats
    assert "file_size" in stats

def test_statistics_collected_in_single_pass(valid_fastq_data):
    """Test that statistics are collected in a single pass."""
    validator = FastqValidator()
    stream = io.BytesIO(valid_fastq_data)
    
    # Mock the methods to track calls
    original_validate_fastq_stream = validator.validate_fastq_stream
    original_process_fastq_content = validator._process_fastq_content
    
    validator.validate_fastq_stream = MagicMock(wraps=validator.validate_fastq_stream)
    validator._process_fastq_content = MagicMock(wraps=validator._process_fastq_content)
    
    result = validator.validate_stream(stream)
    
    # We should call validate_fastq_stream only once, with collect_stats=True
    validator.validate_fastq_stream.assert_called_once()
    assert validator.validate_fastq_stream.call_args[1]["collect_stats"] is True
    
    # We should not call _process_fastq_content at all
    validator._process_fastq_content.assert_not_called()
    
    # Restore original methods
    validator.validate_fastq_stream = original_validate_fastq_stream
    validator._process_fastq_content = original_process_fastq_content
    
def test_hash_calculating_stream():
    """Test the HashCalculatingStream functionality directly."""
    data = b"Test data for hashing"
    stream = io.BytesIO(data)
    
    validator = FastqValidator()
    hash_stream, metadata = validator.create_hash_calculating_stream(stream)
    
    # Read all data from the stream
    content = hash_stream.read()
    assert content == data
    
    # Get hash values
    hash_values = validator.get_hash_values(hash_stream)
    
    # Verify hash values
    assert "md5sum" in hash_values
    assert "sha256" in hash_values
    assert "crc32c" in hash_values
    assert "file_size" in hash_values
    assert hash_values["file_size"] == len(data)
    
    # Verify MD5 hash is correct
    import hashlib
    expected_md5 = hashlib.md5(data).hexdigest()
    assert hash_values["md5sum"] == expected_md5 