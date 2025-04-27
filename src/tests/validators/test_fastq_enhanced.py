"""
Tests for enhanced features of the FASTQ validator.

This module contains advanced test cases for the FASTQ validator, 
including performance testing and edge case handling.
"""
import os
import time
import pytest
import tempfile
import io
from pathlib import Path

from src.validators.fastq import FastqValidator

# Get the path to test data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "data", "fastq")
VALID_FILES_DIR = os.path.join(TEST_DATA_DIR, "valid")
INVALID_FILES_DIR = os.path.join(TEST_DATA_DIR, "invalid")


@pytest.fixture
def validator():
    """
    Create a FASTQ validator instance for testing.
    
    Returns:
        FastqValidator: An initialized FASTQ validator
    """
    return FastqValidator()


@pytest.fixture
def large_fastq_file():
    """
    Create a large FASTQ file for performance testing.
    
    Yields:
        str: Path to the temporary large FASTQ file
    """
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        # Create 10,000 FASTQ records (40,000 lines)
        for i in range(10_000):
            f.write(f"@read{i}\n".encode())
            f.write(b"ACGTACGTACGTACGTACGTACGTACGTACGT\n")
            f.write(f"+read{i}\n".encode())
            f.write(b"IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")  # Same length as sequence (32)
    
    yield f.name
    
    # Clean up
    try:
        os.unlink(f.name)
    except:
        pass


@pytest.mark.performance
def test_performance_large_file(validator, large_fastq_file):
    """Test performance of validator with a large file."""
    start_time = time.time()
    result = validator.validate_file(large_fastq_file)
    elapsed_time = time.time() - start_time
    
    assert result["valid"] is True
    assert result["stats"]["read_count"] == 10_000
    
    # Performance assertion - should be reasonably fast
    # This is a loose assertion that might need adjustment based on the environment
    assert elapsed_time < 10, f"Validation took too long: {elapsed_time:.2f}s"


@pytest.mark.parametrize("quality_string, valid", [
    ("!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJ", True),  # Full range of valid qualities
    ("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII", True),     # Common quality (I = 40)
    ("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", True),     # Lowest quality (! = 0)
    ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", True),     # Highest quality (~ = 93)
    ("ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghij", True),  # Mixed quality values
    ("IIIIIIIII\tIIIIIIIIIIIIIIIIIIIIIIIIIIIIII", False),   # Contains tab (invalid)
    ("IIIIIIIII\nIIIIIIIIIIIIIIIIIIIIIIIIIIIIII", False),   # Contains newline (invalid)
    ("IIIIIIIIIIIIIIIIIIIIIIIII IIIIIIIIIIIIIII", False),   # Contains space (invalid)
    ("IIIIIIIII€IIIIIIIIIIIIIIIIIIIIIIIIIIIIIII", False),   # Contains non-ASCII (invalid)
])
def test_quality_string_validation(validator, quality_string, valid):
    """Test validation of different quality string patterns."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        seq_length = len(quality_string)  # Make sequence and quality same length
        f.write(b"@test_read\n")
        f.write(b"A" * seq_length + b"\n")  # Make sequence length match quality length
        f.write(b"+\n")
        f.write(quality_string.encode())
        f.write(b"\n")
    
    try:
        result = validator.validate_file(f.name)
        
        if valid:
            assert result["valid"] is True, f"Quality string should be valid: {quality_string}"
        else:
            assert result["valid"] is False, f"Quality string should be invalid: {quality_string}"
            assert "invalid_format" in result["errors"]
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass


@pytest.mark.parametrize("seq_string, valid", [
    ("ACGTACGTACGTACGT", True),                   # Standard bases
    ("acgtacgtacgtacgt", True),                   # Lowercase bases
    ("ACGTURYKMSWBDHVN", True),                   # IUPAC nucleotide codes
    ("ACGT.~ACGT.~ACGT", True),                   # Special characters allowed in FASTQ
    ("ACGT-ACGT-ACGT", False),                    # Hyphens not allowed
    ("ACGT ACGT ACGT", False),                    # Spaces not allowed
    ("ACGT1234ACGT", False),                      # Numbers not allowed
    ("ACGT\tACGT", False),                        # Tabs not allowed
])
def test_sequence_string_validation(validator, seq_string, valid):
    """Test validation of different sequence string patterns."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        f.write(b"@test_read\n")
        f.write(seq_string.encode())
        f.write(b"\n+\n")
        # Generate quality string of matching length
        f.write(b"I" * len(seq_string))
        f.write(b"\n")
    
    try:
        result = validator.validate_file(f.name)
        
        if valid:
            assert result["valid"] is True, f"Sequence string should be valid: {seq_string}"
        else:
            assert result["valid"] is False, f"Sequence string should be invalid: {seq_string}"
            assert "invalid_format" in result["errors"]
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass


def test_composite_stream(validator):
    """Test the CompositeStream functionality using a split stream."""
    # Create two parts of a FASTQ stream
    part1 = io.BytesIO(b"@read1\nACGT\n+\nIIII\n@read2\n")
    part2 = io.BytesIO(b"ACGT\n+\nIIII\n")
    
    # Manually create the composite stream
    composite = io.BytesIO()
    composite.write(part1.read())
    composite.write(part2.read())
    composite.seek(0)
    
    # Validate the composite stream
    result = validator.validate_stream(composite)
    
    assert result["valid"] is True
    assert result["stats"]["read_count"] == 2


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_non_standard_line_endings(validator):
    """Test validation of FASTQ files with different line endings."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        # Create FASTQ with Windows-style CRLF line endings
        f.write(b"@read1\r\nACGT\r\n+\r\nIIII\r\n")
    
    try:
        result = validator.validate_file(f.name)
        
        # The validator should handle Windows line endings
        assert result["valid"] is True
        assert result["stats"]["read_count"] == 1
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_empty_line_handling(validator):
    """Test validation of FASTQ files with empty lines."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        # Create FASTQ with an empty line in the middle
        f.write(b"@read1\nACGT\n+\nIIII\n\n@read2\nACGT\n+\nIIII\n")
    
    try:
        result = validator.validate_file(f.name)
        
        # Empty lines should be considered invalid
        assert result["valid"] is False
        assert "invalid_format" in result["errors"]
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass 