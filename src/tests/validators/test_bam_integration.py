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


@pytest.fixture
def validator():
    """
    Create a BAM validator instance for testing.
    
    Returns:
        BamValidator: An initialized BAM validator
    """
    return BamValidator()


def test_validate_valid_bam(validator):
    """Test validating valid BAM files."""
    # Test for each valid BAM file in the directory
    for bam_file in os.listdir(BAM_VALID_DIR):
        if bam_file.endswith('.bam'):
            valid_bam = os.path.join(BAM_VALID_DIR, bam_file)
            
            result = validator.validate_file(valid_bam)
            
            assert result["valid"] is True, f"File {bam_file} should be valid"
            assert len(result["errors"]) == 0


def test_validate_invalid_bam_files(validator):
    """Test validating invalid BAM files."""
    # Test for each invalid BAM file in the directory
    for bam_file in os.listdir(BAM_INVALID_DIR):
        if bam_file.endswith('.bam'):
            invalid_bam = os.path.join(BAM_INVALID_DIR, bam_file)
            
            result = validator.validate_file(invalid_bam)
            
            assert result["valid"] is False, f"File {bam_file} should be invalid"
            assert "invalid_format" in result["errors"]


def test_validate_corrupted_header_bam(validator):
    """Test validating a BAM file with corrupted header."""
    # Look for a file with 'badheader' in the name
    corrupted_header_files = [f for f in os.listdir(BAM_INVALID_DIR) 
                             if 'badheader' in f.lower() and f.endswith('.bam')]
    
    if not corrupted_header_files:
        pytest.skip("No corrupted header BAM file found")
    
    corrupted_bam = os.path.join(BAM_INVALID_DIR, corrupted_header_files[0])
    
    result = validator.validate_file(corrupted_bam)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_truncated_bam(validator):
    """Test validating a truncated BAM file."""
    # Look for a file with 'badeof' in the name (bad end of file/truncated)
    truncated_files = [f for f in os.listdir(BAM_INVALID_DIR) 
                      if 'badeof' in f.lower() and f.endswith('.bam')]
    
    if not truncated_files:
        pytest.skip("No truncated BAM file found")
    
    truncated_bam = os.path.join(BAM_INVALID_DIR, truncated_files[0])
    
    result = validator.validate_file(truncated_bam)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_notargets_bam(validator):
    """Test validating a BAM file with no targets."""
    # Look for a file with 'notargets' in the name
    notargets_files = [f for f in os.listdir(BAM_INVALID_DIR) 
                       if 'notargets' in f.lower() and f.endswith('.bam')]
    
    if not notargets_files:
        pytest.skip("No notargets BAM file found")
    
    notargets_bam = os.path.join(BAM_INVALID_DIR, notargets_files[0])
    
    result = validator.validate_file(notargets_bam)
    
    assert result["valid"] is False
    assert "invalid_format" in result["errors"]


def test_validate_specific_ok_bams(validator):
    """Test validating specific known good BAM files."""
    ok_files = ['3.quickcheck.ok.bam', '4.quickcheck.ok.bam']
    
    for ok_file in ok_files:
        file_path = os.path.join(BAM_VALID_DIR, ok_file)
        if not os.path.exists(file_path):
            continue
            
        result = validator.validate_file(file_path)
        
        assert result["valid"] is True, f"Known good file {ok_file} should validate"
        assert len(result["errors"]) == 0


def test_validate_valid_bam_stream(validator):
    """Test validating a valid BAM stream."""
    # Get the first valid BAM file
    valid_files = [f for f in os.listdir(BAM_VALID_DIR) if f.endswith('.bam')]
    
    if not valid_files:
        pytest.skip("No valid BAM files found")
    
    valid_bam = os.path.join(BAM_VALID_DIR, valid_files[0])
    
    with open(valid_bam, "rb") as f:
        bam_content = f.read()
    
    # Create an in-memory stream from the file content
    from io import BytesIO
    stream = BytesIO(bam_content)
    
    result = validator.validate_stream(stream)
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0 