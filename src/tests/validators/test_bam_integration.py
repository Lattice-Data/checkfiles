"""
Integration tests for the BAM validator with samtools.

This module contains integration tests for validating BAM files using the BamValidator.
Tests use actual BAM files and require samtools to be installed.
"""
import os
import pytest
import shutil
import subprocess
from pathlib import Path

from src.validators.bam import BamValidator

# Get the path to test data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "data")
BAM_VALID_DIR = os.path.join(TEST_DATA_DIR, "bam", "valid")
BAM_INVALID_DIR = os.path.join(TEST_DATA_DIR, "bam", "invalid")


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
    if not os.path.exists(os.path.join(BAM_VALID_DIR, "small.bam")):
        try:
            subprocess.run(["bash", download_script], check=True)
        except subprocess.SubprocessError:
            pytest.skip("Failed to download test data")
    
    # Verify test files exist
    if not os.path.exists(os.path.join(BAM_VALID_DIR, "small.bam")):
        pytest.skip("Test data is missing")
        
    return True


@pytest.fixture
def validator():
    """
    Create a BAM validator instance for testing.
    
    Returns:
        BamValidator: An initialized BAM validator
    """
    return BamValidator()


def test_validate_valid_bam(validator, ensure_test_data):
    """Test validating a valid BAM file."""
    valid_bam = os.path.join(BAM_VALID_DIR, "small.bam")
    
    # Skip if test file doesn't exist
    if not os.path.exists(valid_bam):
        pytest.skip(f"Test file not found: {valid_bam}")
    
    result = validator.validate_file(valid_bam)
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0


def test_validate_corrupted_header_bam(validator, ensure_test_data):
    """Test validating a BAM file with corrupted header."""
    corrupted_bam = os.path.join(BAM_INVALID_DIR, "corrupted_header.bam")
    
    # Skip if test file doesn't exist
    if not os.path.exists(corrupted_bam):
        pytest.skip(f"Test file not found: {corrupted_bam}")
    
    result = validator.validate_file(corrupted_bam)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_truncated_bam(validator, ensure_test_data):
    """Test validating a truncated BAM file."""
    truncated_bam = os.path.join(BAM_INVALID_DIR, "truncated.bam")
    
    # Skip if test file doesn't exist
    if not os.path.exists(truncated_bam):
        pytest.skip(f"Test file not found: {truncated_bam}")
    
    result = validator.validate_file(truncated_bam)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_valid_bam_stream(validator, ensure_test_data):
    """Test validating a valid BAM stream."""
    valid_bam = os.path.join(BAM_VALID_DIR, "small.bam")
    
    # Skip if test file doesn't exist
    if not os.path.exists(valid_bam):
        pytest.skip(f"Test file not found: {valid_bam}")
    
    with open(valid_bam, "rb") as f:
        bam_content = f.read()
    
    # Create an in-memory stream from the file content
    from io import BytesIO
    stream = BytesIO(bam_content)
    
    result = validator.validate_stream(stream)
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0 