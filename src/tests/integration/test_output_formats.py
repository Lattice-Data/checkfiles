"""Integration tests for checkfiles output formats."""

import os
import json
import pytest
from pathlib import Path


def test_progress_log_format(valid_fastq_files, temp_log_dir, run_checkfiles):
    """Test the format of the validation_progress.log file."""
    # Find a valid file for testing
    assert valid_fastq_files, "No valid FASTQ files found in test directory"
    fastq_file = valid_fastq_files[0]
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run checkfiles
    result = run_checkfiles([
        "-l", str(fastq_file),
        "-f", "fastq"
    ], env=env)
    
    # Check progress log structure
    progress_log = temp_log_dir / "validation_progress.log"
    assert progress_log.exists(), "Progress log should be created"
    
    with open(progress_log, 'r') as f:
        lines = f.readlines()
        assert len(lines) >= 1, "Progress log should have at least a header"
        
        # Check header format
        header = lines[0].strip().split('\t')
        expected_columns = [
            "identifier", "uri", "errors", "results", 
            "json_patch", "Lattice patched?", "S3 tag patched?"
        ]
        
        for col in expected_columns:
            assert col in header, f"Header should contain {col}"
        
        # Check data row format if present
        if len(lines) > 1:
            data_row = lines[1].strip().split('\t')
            assert len(data_row) >= len(header), "Data row should have at least as many columns as header"
            
            # Test JSON validity of key fields
            errors_json = json.loads(data_row[2])
            assert isinstance(errors_json, (dict, list)), "Errors should be valid JSON"
            
            results_json = json.loads(data_row[3])
            assert isinstance(results_json, dict), "Results should be valid JSON dict"
            
            patch_json = json.loads(data_row[4])
            assert isinstance(patch_json, dict), "JSON patch should be valid JSON dict"


def test_custom_log_file(valid_fastq_files, temp_log_dir, run_checkfiles):
    """Test specifying a custom log file location."""
    assert valid_fastq_files, "No valid FASTQ files found in test directory"
    fastq_file = valid_fastq_files[0]
    custom_log = temp_log_dir / "custom_debug.log"
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run with custom log file
    result = run_checkfiles([
        "-l", str(fastq_file),
        "-f", "fastq",
        "--log-file", str(custom_log)
    ], env=env)
    
    assert result.returncode == 0
    assert custom_log.exists(), "Custom log file should be created"
    
    # Check that the log file has content
    with open(custom_log, 'r') as f:
        content = f.read()
        assert len(content) > 0, "Log file should have content"


def test_quiet_mode(valid_fastq_files, temp_log_dir, run_checkfiles):
    """Test the quiet mode (--quiet) for suppressing progress output."""
    assert valid_fastq_files, "No valid FASTQ files found in test directory"
    fastq_file = valid_fastq_files[0]
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run with quiet flag
    result = run_checkfiles([
        "-l", str(fastq_file),
        "-f", "fastq",
        "--quiet"
    ], env=env)
    
    # Should still work, but with less output
    assert result.returncode == 0
    
    # Progress log should still be created
    progress_log = temp_log_dir / "validation_progress.log"
    assert progress_log.exists(), "Progress log should be created even in quiet mode"


def test_output_contains_file_stats(valid_fastq_files, temp_log_dir, run_checkfiles):
    """Test that the output contains file statistics."""
    assert valid_fastq_files, "No valid FASTQ files found in test directory"
    fastq_file = valid_fastq_files[0]
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run checkfiles
    result = run_checkfiles([
        "-l", str(fastq_file),
        "-f", "fastq"
    ], env=env)
    
    # If validation was successful
    if "Files with valid content: 1" in result.stdout:
        # Check progress log for detailed stats
        progress_log = temp_log_dir / "validation_progress.log"
        with open(progress_log, 'r') as f:
            lines = f.readlines()
            if len(lines) > 1:
                result_line = lines[1].strip().split('\t')
                results = json.loads(result_line[3])
                
                # Check for common file stats in the progress log
                expected_stats = ["file_size", "md5sum", "sha256", "crc32c", "read_count", "read_length"]
                found_any_stat = False
                
                for stat in expected_stats:
                    if stat in results:
                        found_any_stat = True
                        break
                
                assert found_any_stat, "Results should contain at least one file statistic" 