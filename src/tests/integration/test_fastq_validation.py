"""Integration tests for FASTQ file validation."""

import json
import os
import pytest
from pathlib import Path


def test_valid_fastq_local_validation(valid_fastq_files, temp_log_dir, run_checkfiles):
    """Test validation of a valid local FASTQ file."""
    assert valid_fastq_files, "No valid FASTQ files found in test directory"
    
    valid_fastq_file = valid_fastq_files[0]  # Use the first available file
    
    # Set up environment
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run checkfiles
    result = run_checkfiles([
        "-l", str(valid_fastq_file),
        "-f", "fastq",
        "--log-file", str(temp_log_dir / "test.log")
    ], env=env)
    
    # Verify output
    assert result.returncode == 0
    assert "Files with valid content: 1" in result.stdout
    
    # Check log files
    progress_log = temp_log_dir / "validation_progress.log"
    assert progress_log.exists()
    
    # Parse progress log to verify validation completed
    with open(progress_log, 'r') as f:
        lines = f.readlines()
        assert len(lines) > 1, "Progress log should contain at least header and one result"


def test_invalid_fastq_validation(invalid_fastq_files, temp_log_dir, run_checkfiles):
    """Test validation of an invalid FASTQ file."""
    assert invalid_fastq_files, "No invalid FASTQ files found in test directory"
    
    invalid_fastq_file = invalid_fastq_files[0]  # Use the first available invalid file
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run checkfiles on invalid file
    result = run_checkfiles([
        "-l", str(invalid_fastq_file),
        "-f", "fastq"
    ], env=env)
    
    # For invalid files, check that validation shows failure
    assert "Files with invalid content: 1" in result.stdout or "Files that failed processing" in result.stdout
    
    # Check progress log for errors
    progress_log = temp_log_dir / "validation_progress.log"
    with open(progress_log, 'r') as f:
        lines = f.readlines()
        if len(lines) > 1:
            result_line = lines[1].strip().split('\t')
            errors = json.loads(result_line[2])
            assert errors, "Should have validation errors"


def test_multiple_fastq_files(valid_fastq_files, temp_log_dir, run_checkfiles):
    """Test validation of multiple FASTQ files."""
    assert valid_fastq_files, "No valid FASTQ files found in test directory"
    
    # Use up to 3 valid files
    test_files = valid_fastq_files[:3]
    
    # Join file paths with commas
    file_list = ",".join(str(f) for f in test_files)
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run checkfiles
    result = run_checkfiles([
        "-l", file_list,
        "-f", "fastq"
    ], env=env)
    
    # Check for number of files in the output
    assert f"Starting validation of {len(test_files)} files" in result.stdout
    assert f"Total files submitted: {len(test_files)}" in result.stdout
    
    # Check validation results in progress log
    progress_log = temp_log_dir / "validation_progress.log"
    with open(progress_log, 'r') as f:
        lines = f.readlines()
        # Should have header + one line per file
        assert len(lines) == len(test_files) + 1, "Progress log should have one entry per file"


def test_output_format(valid_fastq_files, temp_log_dir, run_checkfiles):
    """Test the format of the output logs."""
    assert valid_fastq_files, "No valid FASTQ files found in test directory"
    fastq_file = valid_fastq_files[0]
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    result = run_checkfiles([
        "-l", str(fastq_file),
        "-f", "fastq"
    ], env=env)
    
    # Check the progress log structure
    progress_log = temp_log_dir / "validation_progress.log"
    with open(progress_log, 'r') as f:
        lines = f.readlines()
        
        # First line should be the header
        header = lines[0].strip().split('\t')
        assert "identifier" in header
        assert "uri" in header
        assert "errors" in header
        assert "results" in header
        assert "json_patch" in header
        
        # Second line should contain the results
        if len(lines) > 1:
            result_line = lines[1].strip().split('\t')
            assert len(result_line) >= 5, "Result line should have at least 5 columns"
            
            # Verify results field contains JSON data
            results_json = json.loads(result_line[3])
            assert isinstance(results_json, dict)
            
            # Check if specific FASTQ metrics are present
            if result.returncode == 0:  # Only if validation passed
                assert "read_count" in results_json or "file_size" in results_json


def test_multithreading(valid_fastq_files, temp_log_dir, run_checkfiles):
    """Test checkfiles with multiple threads."""
    # Need at least 2 files for thread testing
    if len(valid_fastq_files) < 2:
        pytest.skip("Need at least 2 FASTQ files for thread testing")
    
    # Take first 3 files or fewer if not enough
    test_files = valid_fastq_files[:min(3, len(valid_fastq_files))]
    file_list = ",".join(str(f) for f in test_files)
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run with explicit thread count
    result = run_checkfiles([
        "-l", file_list,
        "-f", "fastq",
        "--threads", "2"  # Use 2 threads
    ], env=env)
    
    # Verify output mentions thread count
    assert "Using 2 threads for parallel file processing" in result.stdout
    
    # Check for number of files in the output
    assert f"Starting validation of {len(test_files)} files" in result.stdout
    assert f"Total files submitted: {len(test_files)}" in result.stdout 