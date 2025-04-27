"""
Integration tests for the CRAM validator with samtools.

This module contains integration tests for validating CRAM files using the CramValidator.
Tests use actual CRAM files and require samtools to be installed.
"""
import os
import pytest
import shutil
import subprocess
from pathlib import Path

from src.validators.cram import CramValidator

# Get the path to test data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "data")
CRAM_VALID_DIR = os.path.join(TEST_DATA_DIR, "cram", "valid")
CRAM_INVALID_DIR = os.path.join(TEST_DATA_DIR, "cram", "invalid")


def is_samtools_available():
    """Check if samtools is available in the system."""
    try:
        subprocess.run(["samtools", "--version"], 
                       stdout=subprocess.PIPE, 
                       stderr=subprocess.PIPE, 
                       check=False)
        return True
    except FileNotFoundError:
        return False


# Skip all tests if samtools is not available
pytestmark = pytest.mark.skipif(
    not is_samtools_available(),
    reason="Samtools is not available in the system"
)


@pytest.fixture(scope="module")
def ensure_test_data():
    """
    Ensure test data is available by running the download script.
    
    Returns:
        bool: True if test data is available and ready for testing
    """
    download_script = os.path.join(TEST_DATA_DIR, "download_test_data.sh")
    
    # Check if download script exists
    if not os.path.exists(download_script):
        pytest.skip("Test data download script not found")
    
    # Run the download script if test data doesn't exist
    if not os.path.exists(os.path.join(CRAM_VALID_DIR, "small.cram")):
        try:
            subprocess.run(["bash", download_script], check=True)
        except subprocess.SubprocessError:
            pytest.skip("Failed to download test data")
    
    # Verify test files exist
    if not os.path.exists(os.path.join(CRAM_VALID_DIR, "small.cram")):
        pytest.skip("Test data is missing")
        
    return True


@pytest.fixture
def validator():
    """
    Create a CRAM validator instance for testing.
    
    Returns:
        CramValidator: An initialized CRAM validator
    """
    return CramValidator()


def test_validate_valid_cram(validator, ensure_test_data):
    """Test validating a valid CRAM file."""
    valid_cram = os.path.join(CRAM_VALID_DIR, "small.cram")
    
    # Skip if test file doesn't exist
    if not os.path.exists(valid_cram):
        pytest.skip(f"Test file not found: {valid_cram}")
    
    result = validator.validate_file(valid_cram)
    
    # Note: CRAM validation might fail if reference genome is not available
    # In this case, we'll check for specific errors
    if not result["valid"]:
        error_msg = result["errors"].get("invalid_format", "")
        if "reference" in error_msg.lower():
            pytest.skip("CRAM validation requires reference genome")
    else:
        assert result["valid"] is True
        assert len(result["errors"]) == 0


def test_validate_corrupted_header_cram(validator, ensure_test_data):
    """Test validating a CRAM file with corrupted header."""
    corrupted_cram = os.path.join(CRAM_INVALID_DIR, "corrupted_header.cram")
    
    # Skip if test file doesn't exist
    if not os.path.exists(corrupted_cram):
        pytest.skip(f"Test file not found: {corrupted_cram}")
    
    result = validator.validate_file(corrupted_cram)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_truncated_cram(validator, ensure_test_data):
    """Test validating a truncated CRAM file."""
    truncated_cram = os.path.join(CRAM_INVALID_DIR, "truncated.cram")
    
    # Skip if test file doesn't exist
    if not os.path.exists(truncated_cram):
        pytest.skip(f"Test file not found: {truncated_cram}")
    
    result = validator.validate_file(truncated_cram)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_valid_cram_stream(validator, ensure_test_data):
    """Test validating a valid CRAM stream."""
    valid_cram = os.path.join(CRAM_VALID_DIR, "small.cram")
    
    # Skip if test file doesn't exist
    if not os.path.exists(valid_cram):
        pytest.skip(f"Test file not found: {valid_cram}")
    
    with open(valid_cram, "rb") as f:
        cram_content = f.read()
    
    # Create an in-memory stream from the file content
    from io import BytesIO
    stream = BytesIO(cram_content)
    
    result = validator.validate_stream(stream)
    
    # Note: CRAM validation might fail if reference genome is not available
    # In this case, we'll check for specific errors
    if not result["valid"]:
        error_msg = result["errors"].get("invalid_format", "")
        if "reference" in error_msg.lower():
            pytest.skip("CRAM validation requires reference genome")
    else:
        assert result["valid"] is True
        assert len(result["errors"]) == 0 