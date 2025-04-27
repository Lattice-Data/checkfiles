"""
Tests for the FASTQ validator with pure Python implementation.

This module contains test cases for validating FASTQ files using the FastqValidator.
Tests cover validation of file formats, error conditions, and statistics collection.
"""
import os
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
def test_files():
    """
    Create temporary FASTQ files for testing.
    
    Returns:
        dict: Dictionary containing paths to test files
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a simple valid FASTQ file
        temp_fastq = os.path.join(temp_dir, "test.fastq")
        with open(temp_fastq, "w") as f:
            f.write("@read1\n")
            f.write("ACGTACGT\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            f.write("@read2\n")
            f.write("GCTAGCTA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
        
        # Create an invalid FASTQ file for testing
        invalid_fastq = os.path.join(temp_dir, "invalid.fastq")
        with open(invalid_fastq, "w") as f:
            f.write("Not a FASTQ file\n")
            f.write("Just some random text\n")
            
        # Create an empty file
        empty_fastq = os.path.join(temp_dir, "empty.fastq")
        with open(empty_fastq, "w") as f:
            pass
            
        # Create a FASTQ file with short reads
        short_fastq = os.path.join(temp_dir, "short.fastq")
        with open(short_fastq, "w") as f:
            f.write("@read1\n")
            f.write("AC\n")  # Very short read
            f.write("+\n")
            f.write("II\n")
            
        # Create a FASTQ file with variable length reads
        var_fastq = os.path.join(temp_dir, "variable.fastq")
        with open(var_fastq, "w") as f:
            f.write("@read1\n")
            f.write("ACGT\n")
            f.write("+\n")
            f.write("IIII\n")
            f.write("@read2\n")
            f.write("ACGTACGTACGT\n")  # 3x longer read
            f.write("+\n")
            f.write("IIIIIIIIIIII\n")
            
        # Create a file with a specific error - header line without @
        bad_header_fastq = os.path.join(temp_dir, "bad_header.fastq")
        with open(bad_header_fastq, "w") as f:
            f.write("read1 without @ symbol\n")  # Missing @ in header
            f.write("ACGT\n")
            f.write("+\n")
            f.write("IIII\n")
            
        # Create a file with an error in a specific line
        line_error_fastq = os.path.join(temp_dir, "line_error.fastq")
        with open(line_error_fastq, "w") as f:
            f.write("@read1\n")
            f.write("ACGT\n")
            f.write("+\n")
            f.write("IIII\n")
            f.write("@read2\n")
            f.write("ACGT\n")
            f.write("MISSING_PLUS_SYMBOL\n")  # Error on line 7 - missing +
            f.write("IIII\n")
        
        yield {
            "valid": temp_fastq,
            "invalid": invalid_fastq,
            "empty": empty_fastq,
            "short": short_fastq,
            "variable": var_fastq,
            "bad_header": bad_header_fastq,
            "line_error": line_error_fastq,
            "temp_dir": temp_dir
        }


def test_validate_file_valid(validator, test_files):
    """Test validating a valid FASTQ file."""
    result = validator.validate_file(test_files["valid"])
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0
    
    # Verify statistics
    stats = result["stats"]
    assert stats["read_count"] == 2
    assert stats["total_length"] == 16
    assert stats["min_length"] == 8
    assert stats["max_length"] == 8


def test_validate_file_invalid(validator, test_files):
    """Test validating an invalid FASTQ file."""
    result = validator.validate_file(test_files["invalid"])
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_file_not_found(validator):
    """Test validating a non-existent file."""
    result = validator.validate_file("/path/to/nonexistent/file.fastq")
    
    assert result["valid"] is False
    assert "file_not_found" in result["errors"]


def test_validate_stream_valid(validator):
    """Test validating a valid FASTQ stream."""
    # Create a valid FASTQ stream
    stream_content = b"@read1\nACGT\n+\nIIII\n@read2\nACGT\n+\nIIII\n"
    input_stream = io.BytesIO(stream_content)
    
    result = validator.validate_stream(input_stream)
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0
    
    # Verify statistics
    stats = result["stats"]
    assert stats["read_count"] == 2
    assert stats["total_length"] == 8
    assert stats["min_length"] == 4
    assert stats["max_length"] == 4


def test_validate_stream_invalid(validator):
    """Test validating an invalid FASTQ stream."""
    # Create an invalid stream
    stream_content = b"This is not a valid FASTQ file"
    input_stream = io.BytesIO(stream_content)
    
    result = validator.validate_stream(input_stream)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_empty_file(validator, test_files):
    """Test validating an empty FASTQ file."""
    result = validator.validate_file(test_files["empty"])
    
    assert result["valid"] is False
    assert "empty_file" in result["errors"]


def test_validate_short_reads(validator, test_files):
    """Test validating FASTQ with very short reads."""
    result = validator.validate_file(test_files["short"])
    
    assert result["valid"] is True  # Short reads are a warning, not an error
    assert "short_reads" in result["warnings"]


def test_validate_variable_length_reads(validator, test_files):
    """Test validating FASTQ with variable length reads."""
    result = validator.validate_file(test_files["variable"])
    
    assert result["valid"] is True
    assert "variable_length" in result["warnings"]


def test_error_message_content(validator, test_files):
    """Test that specific error messages are included in the validation results."""
    result = validator.validate_file(test_files["bad_header"])
    
    assert result["valid"] is False
    # Verify the error message contains specific information
    assert "Header line must start with @" in result["errors"]["invalid_format"]
    # Verify the line number is reported
    assert "at line 1" in result["errors"]["invalid_format"]


def test_line_number_reporting(validator, test_files):
    """Test that line numbers are correctly reported in validation errors."""
    result = validator.validate_file(test_files["line_error"])
    
    assert result["valid"] is False
    # Check that line 7 is mentioned in the error message
    assert "at line 7" in result["errors"]["invalid_format"]


def test_stream_error_details(validator):
    """Test that stream validation provides detailed error information."""
    # Create a stream with a specific error - quality length mismatch
    stream_content = b"@read1\nACGTACGT\n+\nIII\n"  # Quality length (3) doesn't match sequence (8)
    input_stream = io.BytesIO(stream_content)
    
    result = validator.validate_stream(input_stream)
    
    assert result["valid"] is False
    # Verify error contains details about the length mismatch
    assert "length" in result["errors"]["invalid_format"].lower()
    assert "don't match" in result["errors"]["invalid_format"]


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_all_valid_files(validator):
    """Test validating all valid FASTQ files in the test data directory."""
    if not os.path.exists(VALID_FILES_DIR):
        pytest.skip(f"Valid files directory not found: {VALID_FILES_DIR}")
    
    valid_files = [f for f in os.listdir(VALID_FILES_DIR) if f.endswith('.fastq')]
    
    for filename in valid_files:
        file_path = os.path.join(VALID_FILES_DIR, filename)
        result = validator.validate_file(file_path)
        
        assert result["valid"], f"File should be valid: {filename}"
        assert len(result["errors"]) == 0, f"No errors should be present for: {filename}"


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_all_invalid_files(validator):
    """Test validating all invalid FASTQ files in the test data directory."""
    if not os.path.exists(INVALID_FILES_DIR):
        pytest.skip(f"Invalid files directory not found: {INVALID_FILES_DIR}")
    
    invalid_files = [f for f in os.listdir(INVALID_FILES_DIR) if f.endswith('.fastq')]
    
    for filename in invalid_files:
        file_path = os.path.join(INVALID_FILES_DIR, filename)
        result = validator.validate_file(file_path)
        
        # Handle special case: mismatched_ids.fastq is now considered valid with warnings
        if filename == "mismatched_ids.fastq":
            assert result["valid"], f"File should be valid with warnings: {filename}"
            assert len(result["warnings"]) > 0, f"Warnings should be present for: {filename}"
        else:
            assert not result["valid"], f"File should be invalid: {filename}"
            assert len(result["errors"]) > 0, f"Errors should be present for: {filename}"


def test_mismatched_lengths(validator):
    """Test validating a FASTQ file with mismatched sequence/quality lengths."""
    # Create a file with mismatched lengths
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        f.write(b"@read1\n")
        f.write(b"ACGTACGT\n")
        f.write(b"+\n")
        f.write(b"III\n")  # Only 3 quality scores for 8 bases
    
    try:
        result = validator.validate_file(f.name)
        
        assert result["valid"] is False
        assert "invalid_format" in result["errors"]
        assert "length" in result["errors"]["invalid_format"].lower()
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass


def test_missing_at_symbol(validator):
    """Test validating a FASTQ file with a missing @ symbol in header."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        f.write(b"read1\n")  # Missing @ in header
        f.write(b"ACGT\n")
        f.write(b"+\n")
        f.write(b"IIII\n")
    
    try:
        result = validator.validate_file(f.name)
        
        assert result["valid"] is False
        assert "invalid_format" in result["errors"]
        assert "@" in result["errors"]["invalid_format"]
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass


def test_missing_plus(validator):
    """Test validating a FASTQ file with a missing + symbol."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        f.write(b"@read1\n")
        f.write(b"ACGT\n")
        f.write(b"missing_plus\n")  # Missing + separator
        f.write(b"IIII\n")
    
    try:
        result = validator.validate_file(f.name)
        
        assert result["valid"] is False
        assert "invalid_format" in result["errors"]
        assert "+" in result["errors"]["invalid_format"]
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass


def test_mismatched_ids(validator):
    """Test validating a FASTQ file with mismatched ids in header and description lines."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        f.write(b"@read1\n")
        f.write(b"ACGT\n")
        f.write(b"+read2\n")  # Mismatched ID
        f.write(b"IIII\n")
    
    try:
        result = validator.validate_file(f.name)
        
        # According to FASTQ format, mismatched IDs are allowed but should trigger a warning
        assert "mismatched_ids" in result["warnings"]
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass


def test_incomplete_record(validator):
    """Test validating a FASTQ file with incomplete records."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        f.write(b"@read1\n")
        f.write(b"ACGT\n")
        f.write(b"+\n")
        f.write(b"IIII\n")
        f.write(b"@read2\n")
        f.write(b"ACGT\n")
        # Missing + and quality lines
    
    try:
        result = validator.validate_file(f.name)
        
        assert result["valid"] is False
        assert "invalid_format" in result["errors"]
        assert "incomplete" in result["errors"]["invalid_format"].lower()
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass


def test_stream_with_large_data(validator):
    """Test validating a large FASTQ stream to check buffering behavior."""
    # Create a large FASTQ stream with many records
    buffer = io.BytesIO()
    record_count = 100
    
    for i in range(record_count):
        buffer.write(f"@read{i}\n".encode())
        buffer.write(b"ACGTACGTACGTACGT\n")
        buffer.write(f"+read{i}\n".encode())
        buffer.write(b"IIIIIIIIIIIIIIII\n")
    
    buffer.seek(0)
    
    result = validator.validate_stream(buffer)
    
    assert result["valid"] is True
    assert result["stats"]["read_count"] == record_count
    assert result["stats"]["min_length"] == 16
    assert result["stats"]["max_length"] == 16
    assert result["stats"]["total_length"] == 16 * record_count


def test_with_descriptions(validator):
    """Test validating FASTQ with sequence descriptions."""
    with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
        f.write(b"@read1 description with spaces\n")
        f.write(b"ACGT\n")
        f.write(b"+read1 optional description\n")
        f.write(b"IIII\n")
    
    try:
        result = validator.validate_file(f.name)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    finally:
        # Clean up
        try:
            os.unlink(f.name)
        except:
            pass