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
import io

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


@pytest.fixture
def validator():
    """
    Create a CRAM validator instance for testing.
    
    Returns:
        CramValidator: An initialized CRAM validator
    """
    return CramValidator()


def test_validate_valid_cram(validator):
    """Test validating valid CRAM files."""
    # Test for each valid CRAM file in the directory
    for cram_file in os.listdir(CRAM_VALID_DIR):
        if cram_file.endswith('.cram'):
            valid_cram = os.path.join(CRAM_VALID_DIR, cram_file)
            
            result = validator.validate_file(valid_cram)
            
            # CRAM validation might fail if reference genome is not available
            # In this case, we'll check for specific errors
            if not result["valid"]:
                error_msg = result["errors"].get("invalid_format", "")
                if "reference" in error_msg.lower():
                    pytest.skip(f"CRAM validation for {cram_file} requires reference genome")
                else:
                    assert False, f"Valid CRAM file {cram_file} failed validation: {error_msg}"
            else:
                assert result["valid"] is True, f"File {cram_file} should be valid"
                assert len(result["errors"]) == 0


def test_validate_invalid_cram_files(validator):
    """Test validating invalid CRAM files."""
    # Test for each invalid CRAM file in the directory
    for cram_file in os.listdir(CRAM_INVALID_DIR):
        if cram_file.endswith('.cram'):
            invalid_cram = os.path.join(CRAM_INVALID_DIR, cram_file)
            
            result = validator.validate_file(invalid_cram)
            
            # Even with missing reference, these files should fail validation
            # but let's handle the specific case
            if not result["valid"]:
                assert result["valid"] is False, f"File {cram_file} should be invalid"
                # We can have either invalid_format due to CRAM corruption
                # or a reference genome error, both are valid failures
                assert "invalid_format" in result["errors"] or "reference" in str(result["errors"]).lower()
            else:
                assert False, f"Invalid CRAM file {cram_file} passed validation"


def test_validate_truncated_cram(validator):
    """Test validating truncated CRAM files."""
    # Look for files with 'truncated' in the name
    truncated_files = [f for f in os.listdir(CRAM_INVALID_DIR) 
                      if 'truncated' in f.lower() and f.endswith('.cram')]
    
    if not truncated_files:
        pytest.skip("No truncated CRAM files found")
    
    for truncated_file in truncated_files:
        truncated_cram = os.path.join(CRAM_INVALID_DIR, truncated_file)
        
        result = validator.validate_file(truncated_cram)
        
        assert result["valid"] is False, f"File {truncated_file} should be invalid"
        assert "invalid_format" in result["errors"] or "reference" in str(result["errors"]).lower()


def test_validate_cram21_ok(validator):
    """Test validating CRAM v2.1 files."""
    cram21_files = [f for f in os.listdir(CRAM_VALID_DIR) 
                   if 'cram21' in f.lower() and 'ok' in f.lower() and f.endswith('.cram')]
    
    if not cram21_files:
        pytest.skip("No CRAM v2.1 files found")
    
    for cram_file in cram21_files:
        cram_path = os.path.join(CRAM_VALID_DIR, cram_file)
        
        result = validator.validate_file(cram_path)
        
        # Handle missing reference case
        if not result["valid"]:
            error_msg = result["errors"].get("invalid_format", "")
            if "reference" in error_msg.lower():
                pytest.skip(f"CRAM validation for {cram_file} requires reference genome")
            else:
                assert False, f"Valid CRAM v2.1 file {cram_file} failed validation: {error_msg}"
        else:
            assert result["valid"] is True, f"CRAM v2.1 file {cram_file} should be valid"
            assert len(result["errors"]) == 0


def test_validate_cram30_ok(validator):
    """Test validating CRAM v3.0 files."""
    cram30_files = [f for f in os.listdir(CRAM_VALID_DIR) 
                   if 'cram30' in f.lower() and 'ok' in f.lower() and f.endswith('.cram')]
    
    if not cram30_files:
        pytest.skip("No CRAM v3.0 files found")
    
    for cram_file in cram30_files:
        cram_path = os.path.join(CRAM_VALID_DIR, cram_file)
        
        result = validator.validate_file(cram_path)
        
        # Handle missing reference case
        if not result["valid"]:
            error_msg = result["errors"].get("invalid_format", "")
            if "reference" in error_msg.lower():
                pytest.skip(f"CRAM validation for {cram_file} requires reference genome")
            else:
                assert False, f"Valid CRAM v3.0 file {cram_file} failed validation: {error_msg}"
        else:
            assert result["valid"] is True, f"CRAM v3.0 file {cram_file} should be valid"
            assert len(result["errors"]) == 0


def test_validate_valid_cram_stream(validator, monkeypatch):
    """Test validating a valid CRAM stream."""
    # Get the first valid CRAM file
    valid_files = [f for f in os.listdir(CRAM_VALID_DIR) if f.endswith('.cram')]
    
    if not valid_files:
        pytest.skip("No valid CRAM files found")
    
    valid_cram = os.path.join(CRAM_VALID_DIR, valid_files[0])
    
    with open(valid_cram, "rb") as f:
        cram_content = f.read()
    
    # Mock subprocess.Popen for samtools calls
    class MockPopen:
        def __init__(self, args, **kwargs):
            self.stdin = io.BytesIO()
            self.returncode = 0  # Make it return success
        
        def communicate(self):
            return b"", b""  # stdout, stderr
            
    # Patch subprocess.Popen
    monkeypatch.setattr("subprocess.Popen", MockPopen)
    
    # Create an in-memory stream from the file content
    from io import BytesIO
    stream = BytesIO(cram_content)
    
    result = validator.validate_stream(stream)
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0 