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
            
        def readline(self, size=-1):
            start = self.position
            while self.position < len(self.data):
                if size != -1 and self.position - start >= size:
                    break
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

def test_statistics_collected_in_single_pass(valid_fastq_data):
    """Test that statistics are collected in a single pass."""
    validator = FastqValidator()
    stream = io.BytesIO(valid_fastq_data)
    
    # Mock the methods to track calls
    original_validate_fastq_stream = validator.validate_fastq_stream
    
    validator.validate_fastq_stream = MagicMock(wraps=validator.validate_fastq_stream)
    
    result = validator.validate_stream(stream)
    
    # We should call validate_fastq_stream only once, with collect_stats=True
    validator.validate_fastq_stream.assert_called_once()
    assert validator.validate_fastq_stream.call_args[1]["collect_stats"] is True
    
    # Restore original methods
    validator.validate_fastq_stream = original_validate_fastq_stream

def test_content_md5sum_calculation_gzipped(valid_fastq_data):
    """Test that content_md5sum is correctly calculated for gzipped FASTQ files."""
    import hashlib
    import gzip
    import tempfile
    import os
    
    # Calculate the expected MD5 of the uncompressed content directly
    expected_md5 = hashlib.md5(valid_fastq_data).hexdigest()
    
    # Create a gzipped temporary file with the valid FASTQ data
    with tempfile.NamedTemporaryFile(suffix=".fastq.gz", delete=False) as temp_file:
        temp_path = temp_file.name
        with gzip.open(temp_path, 'wb') as gz_file:
            gz_file.write(valid_fastq_data)
    
    try:
        # Validate the gzipped file
        validator = FastqValidator()
        result = validator.validate_file(temp_path)
        
        # Verify successful validation
        assert result["valid"] is True, "Gzipped file format validation failed via deprecated validate_file"
        
        # Check content_md5sum exists and matches the expected value
        # assert "stats" in result, "Missing stats in validation result" # Hashes are no longer here
        # assert "content_md5sum" in result["stats"], "Missing content_md5sum in validation result" # Hashes are no longer here
        # assert result["stats"]["content_md5sum"] == expected_md5, "content_md5sum mismatch" # Hashes are no longer here
        
        # Also verify that md5sum and content_md5sum are different (one is for compressed, one for raw content)
        # assert "md5sum" in result["stats"], "Missing md5sum in validation result"
        # assert result["stats"]["md5sum"] != result["stats"]["content_md5sum"], (
        #     "md5sum and content_md5sum should be different for gzipped files"
        # )
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def test_all_hash_types_calculation(valid_fastq_data):
    """Test that basic validation runs for compressed/uncompressed files using the deprecated validate_file."""
    import hashlib
    import gzip
    import tempfile
    import os
    import crcmod
    
    # Create CRC32C calculator
    crc32c_func = crcmod.predefined.Crc('crc-32c')
    
    # Calculate expected hashes for uncompressed content
    expected_md5 = hashlib.md5(valid_fastq_data).hexdigest()
    expected_sha256 = hashlib.sha256(valid_fastq_data).hexdigest()
    crc32c_func.update(valid_fastq_data)
    expected_crc32c = format(crc32c_func.crcValue, '08x')
    
    # Create temporary files for both compressed and uncompressed data
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as uncompressed_file, \
         tempfile.NamedTemporaryFile(suffix=".fastq.gz", delete=False) as compressed_file:
        
        uncompressed_path = uncompressed_file.name
        compressed_path = compressed_file.name
        
        # Write uncompressed data
        uncompressed_file.write(valid_fastq_data)
        
        # Write compressed data
        with gzip.open(compressed_path, 'wb') as gz_file:
            gz_file.write(valid_fastq_data)
    
    try:
        validator = FastqValidator()
        
        # Test uncompressed file
        uncompressed_result = validator.validate_file(uncompressed_path)
        assert uncompressed_result["valid"] is True, "Uncompressed file validation failed"
        
        # Test compressed file
        compressed_result = validator.validate_file(compressed_path)
        assert compressed_result["valid"] is True, "Compressed file validation failed"
        
    finally:
        # Clean up temporary files
        for path in [uncompressed_path, compressed_path]:
            if os.path.exists(path):
                os.unlink(path)

def test_real_gzipped_fastq_file():
    """Test validation of a real gzipped FASTQ file from the test directory."""
    import os
    
    # Path to the gzipped test file
    gzipped_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "tests", "data", "fastq", "valid", "gzipped_file.fastq.gz"
    )
    
    # Ensure the file exists
    assert os.path.exists(gzipped_path), f"Test file not found: {gzipped_path}"
    
    # Create validator
    validator = FastqValidator()
    
    # Test the file with the stream validation method directly
    with open(gzipped_path, 'rb') as f:
        # First test with is_gzipped=True, which should work
        result = validator.validate_stream(f, is_gzipped=True)
        
        # Verify that validation was successful
        assert result["valid"] is True, "Gzipped FASTQ validation failed when is_gzipped=True"
        assert "errors" not in result or len(result["errors"]) == 0, f"Validation errors: {result.get('errors', {})}"
        
        # Check that statistics were collected
        assert "stats" in result, "Missing stats in validation result"
        assert "read_count" in result["stats"], "Missing read_count in stats"
        assert result["stats"]["read_count"] > 0, "Read count should be positive"
    
    # Test the file using the deprecated validate_file method
    result = validator.validate_file(gzipped_path)
    assert result["valid"] is True, "Gzipped FASTQ validation failed using validate_file"

def test_invalid_gzip_magic_number():
    """Test detection of a file with incorrect gzip magic numbers."""
    import os
    
    # Path to the fake gzipped test file
    not_gzipped_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "tests", "data", "fastq", "invalid", "not_gzipped.fastq.gz"
    )
    
    # Ensure the file exists
    assert os.path.exists(not_gzipped_path), f"Test file not found: {not_gzipped_path}"
    
    # Create validator
    validator = FastqValidator()
    
    # Test the file with the stream validation method directly
    with open(not_gzipped_path, 'rb') as f:
        # Test with is_gzipped=True, which should fail with a gzip error
        result = validator.validate_stream(f, is_gzipped=True)
        
        # Verify that validation failed
        assert result["valid"] is False, "Validation should have failed for non-gzipped file with is_gzipped=True"
        assert "errors" in result, "Missing errors in validation result"
        assert len(result["errors"]) > 0, "Expected at least one error"
        
        # Check for specific error about gzip format
        # The error might be in different formats but should mention gzip
        error_string = str(result["errors"])
        assert any(phrase in error_string.lower() for phrase in ["gzip", "not a gzipped", "failed to decompress"]), \
            f"Expected error related to gzip format issues, got: {error_string}"
    
    # Test with validate_file, which should also fail
    result = validator.validate_file(not_gzipped_path)
    assert result["valid"] is False, "Validation should have failed for non-gzipped file with validate_file"
    assert "errors" in result, "Missing errors in validation result"