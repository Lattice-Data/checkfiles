"""
Tests for the CRAM validator using samtools.

This module contains test cases for validating CRAM files using the CramValidator.
Tests cover validation of file formats, error conditions, and basic functionality.
"""
import os
import pytest
import tempfile
import io
from unittest.mock import patch, MagicMock
from pathlib import Path
import subprocess

from src.validators.cram import CramValidator

# Get the path to test data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "data", "cram")


@pytest.fixture
def validator():
    """
    Create a CRAM validator instance for testing.
    
    Returns:
        CramValidator: An initialized CRAM validator
    """
    # Mock the samtools check to avoid dependency on actual samtools installation during tests
    with patch('subprocess.run') as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        return CramValidator()


@pytest.fixture
def test_files():
    """
    Create temporary CRAM files for testing.
    
    Returns:
        dict: Dictionary containing paths to test files
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create an empty file
        empty_cram = os.path.join(temp_dir, "empty.cram")
        with open(empty_cram, "wb") as f:
            pass
            
        # Create a non-existent file path
        nonexistent_cram = os.path.join(temp_dir, "nonexistent.cram")
        
        yield {
            "empty": empty_cram,
            "nonexistent": nonexistent_cram,
            "temp_dir": temp_dir
        }


def test_validate_file_not_found(validator, test_files):
    """Test validating a non-existent file."""
    result = validator.validate_file(test_files["nonexistent"])
    
    assert result["valid"] is False
    assert "file_not_found" in result["errors"]


def test_validate_empty_file(validator, test_files):
    """Test validating an empty CRAM file."""
    result = validator.validate_file(test_files["empty"])
    
    assert result["valid"] is False
    assert "empty_file" in result["errors"]


@patch('subprocess.run')
def test_validate_file_valid(mock_run, validator, test_files):
    """Test validating a valid CRAM file."""
    # Mock a valid response from samtools quickcheck
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = ""
    mock_process.stderr = ""
    mock_run.return_value = mock_process
    
    # Create a mock CRAM file
    mock_cram = os.path.join(test_files["temp_dir"], "valid.cram")
    with open(mock_cram, "wb") as f:
        f.write(b"mock CRAM content")
    
    result = validator.validate_file(mock_cram)
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0


@patch('subprocess.run')
def test_validate_file_invalid(mock_run, validator, test_files):
    """Test validating an invalid CRAM file."""
    # Mock an invalid response from samtools quickcheck
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = ""
    mock_process.stderr = "Error: corrupt CRAM container"
    mock_run.return_value = mock_process
    
    # Create a mock CRAM file
    mock_cram = os.path.join(test_files["temp_dir"], "invalid.cram")
    with open(mock_cram, "wb") as f:
        f.write(b"invalid CRAM content")
    
    result = validator.validate_file(mock_cram)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]
    assert "corrupt CRAM container" in result["errors"]["invalid_format"]


@patch('subprocess.Popen')
def test_validate_stream_valid(mock_popen, validator):
    """Test validating a valid CRAM stream."""
    # Mock a valid Popen process
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.stdin = MagicMock()
    
    # Set up the mock to return our mock process
    mock_popen.return_value = mock_process
    
    # Create a mock CRAM stream
    stream_content = b"mock CRAM content"
    input_stream = io.BytesIO(stream_content)
    
    result = validator.validate_stream(input_stream)
    
    assert result["valid"] is True
    assert result["stats"]["file_size"] == len(stream_content)
    
    # Verify Popen was called with the right arguments
    mock_popen.assert_called_once_with(
        ["samtools", "quickcheck", "-v", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Verify data was written to stdin
    mock_process.stdin.write.assert_called_with(stream_content)


@patch('subprocess.Popen')
def test_validate_stream_invalid(mock_popen, validator):
    """Test validating an invalid CRAM stream."""
    # Mock an invalid Popen process
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()
    mock_process.communicate.return_value = (b"", b"Error: invalid CRAM file")
    mock_process.stdin = MagicMock()
    
    # Set up the mock to return our mock process
    mock_popen.return_value = mock_process
    
    # Create a mock CRAM stream
    stream_content = b"invalid CRAM content"
    input_stream = io.BytesIO(stream_content)
    
    result = validator.validate_stream(input_stream)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]
    assert "invalid CRAM file" in result["errors"]["invalid_format"]
    assert result["stats"]["file_size"] == len(stream_content)


@patch('subprocess.run')
def test_reference_warning(mock_run, validator, test_files):
    """Test handling of missing reference genome warning for CRAM files."""
    # Mock a response from samtools quickcheck indicating missing reference
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = ""
    mock_process.stderr = "Failed to open reference"
    mock_run.return_value = mock_process
    
    # Create a mock CRAM file
    mock_cram = os.path.join(test_files["temp_dir"], "ref_required.cram")
    with open(mock_cram, "wb") as f:
        f.write(b"CRAM content requiring reference")
    
    result = validator.validate_file(mock_cram)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]
    assert "Failed to open reference" in result["errors"]["invalid_format"]


@patch('subprocess.run')
def test_samtools_error_handling(mock_run, validator, test_files):
    """Test handling of samtools execution errors."""
    # Mock an exception during samtools execution
    mock_run.side_effect = Exception("Command execution failed")
    
    # Create a mock CRAM file
    mock_cram = os.path.join(test_files["temp_dir"], "error.cram")
    with open(mock_cram, "wb") as f:
        f.write(b"CRAM content")
    
    result = validator.validate_file(mock_cram)
    
    assert result["valid"] is False
    assert "validation_error" in result["errors"]
    assert "Command execution failed" in result["errors"]["validation_error"] 