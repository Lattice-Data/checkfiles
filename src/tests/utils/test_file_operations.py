"""Tests for file operation utilities."""

import pytest
import tempfile
import gzip
import io
import os
import shutil
import subprocess
from unittest.mock import patch, MagicMock
from src.utils.helpers.file_operations import (
    has_gz_extension,
    validate_gzip_format,
    stream_local_file,
    stream_s3_file,
    download_s3_file_to_scratch
)
import uuid

def test_has_gz_extension():
    """Test the has_gz_extension function with various file extensions."""
    # Test valid gzip extensions
    assert has_gz_extension("file.gz") is True
    assert has_gz_extension("file.gzip") is True
    assert has_gz_extension("file.GZ") is True  # Test case insensitivity
    assert has_gz_extension("file.GZIP") is True  # Test case insensitivity
    
    # Test invalid extensions
    assert has_gz_extension("file.txt") is False
    assert has_gz_extension("file.fastq") is False
    assert has_gz_extension("file") is False  # No extension
    assert has_gz_extension("") is False  # Empty string

def test_validate_gzip_format():
    """Test the validate_gzip_format function with various file types."""
    # Test with a valid gzip file
    with tempfile.NamedTemporaryFile(suffix='.gz', delete=False) as temp_file:
        with gzip.open(temp_file.name, 'wb') as gz:
            gz.write(b"test content")
        result = validate_gzip_format(temp_file.name)
        assert result == {}  # Empty dict means no errors
    
    # Test with an invalid gzip file (regular text file)
    with tempfile.NamedTemporaryFile(suffix='.gz', delete=False) as temp_file:
        temp_file.write(b"not gzipped content")
        temp_file.flush()
        result = validate_gzip_format(temp_file.name)
        assert 'gzip_error' in result
        assert 'magic number' in result['gzip_error'].lower()
    
    # Test with a non-existent file
    result = validate_gzip_format("nonexistent_file.gz")
    assert 'gzip_error' in result
    assert 'no such file or directory' in result['gzip_error'].lower()
    
    # Test with a directory
    with tempfile.TemporaryDirectory() as temp_dir:
        result = validate_gzip_format(temp_dir)
        assert 'gzip_error' in result
        assert 'is a directory' in result['gzip_error'].lower()

def test_validate_gzip_format_s3():
    """Test the validate_gzip_format function with S3 paths."""
    # Mock subprocess.check_output for successful cases
    with patch('subprocess.check_output') as mock_check_output:
        # Test valid gzip file in S3
        # First call returns magic number, second call verifies header structure
        mock_check_output.side_effect = [
            b'\x1f\x8b',  # First call: magic number
            b''  # Second call: header verification (empty response is fine)
        ]
        result = validate_gzip_format("s3://bucket/valid.gz")
        assert result == {}  # Empty dict means no errors
        
        # Verify the correct commands were used
        assert mock_check_output.call_count == 2
        first_cmd = mock_check_output.call_args_list[0][0][0]
        second_cmd = mock_check_output.call_args_list[1][0][0]
        assert "aws s3 cp s3://bucket/valid.gz - --range 0-1" in first_cmd
        assert "aws s3 cp s3://bucket/valid.gz - --range 0-9 | gunzip -c" in second_cmd
    
    # Test invalid gzip file in S3
    with patch('subprocess.check_output') as mock_check_output:
        mock_check_output.return_value = b'PK'  # Invalid magic number (ZIP format)
        result = validate_gzip_format("s3://bucket/invalid.gz")
        assert 'gzip_error' in result
        assert 'magic number' in result['gzip_error'].lower()
    
    # Test S3 access error
    with patch('subprocess.check_output') as mock_check_output:
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "aws s3 cp", stderr=b"AccessDenied: Access Denied"
        )
        result = validate_gzip_format("s3://bucket/access-denied.gz")
        assert 'gzip_error' in result
        assert 'access denied' in result['gzip_error'].lower()
    
    # Test non-existent S3 file
    with patch('subprocess.check_output') as mock_check_output:
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "aws s3 cp", stderr=b"NoSuchKey: The specified key does not exist"
        )
        result = validate_gzip_format("s3://bucket/nonexistent.gz")
        assert 'gzip_error' in result
        assert 'invalid gzip header structure' in result['gzip_error'].lower()
        assert 'nosuchkey' in result['gzip_error'].lower()

def test_stream_local_file():
    """Test the stream_local_file function with various file types."""
    # Test with a regular text file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
        test_content = b"test content for regular file"
        temp_file.write(test_content)
        temp_file.flush()
        
        # Test without decompression
        with stream_local_file(temp_file.name, decompress=False) as stream:
            content = stream.read()
            assert content == test_content
    
    # Test with a gzipped file
    with tempfile.NamedTemporaryFile(suffix='.gz', delete=False) as temp_file:
        test_content = b"test content for gzipped file"
        with gzip.open(temp_file.name, 'wb') as gz:
            gz.write(test_content)
        
        # Test with automatic decompression (based on extension)
        with stream_local_file(temp_file.name) as stream:
            content = stream.read()
            assert content == test_content
        
        # Test with explicit decompression
        with stream_local_file(temp_file.name, decompress=True) as stream:
            content = stream.read()
            assert content == test_content
        
        # Test without decompression
        with stream_local_file(temp_file.name, decompress=False) as stream:
            content = stream.read()
            assert content != test_content  # Should be compressed content
    
    # Test with non-existent file
    with pytest.raises(FileNotFoundError):
        with stream_local_file("nonexistent_file.txt"):
            pass
    
    # Test with a directory
    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.raises(IsADirectoryError):
            with stream_local_file(temp_dir):
                pass

def test_stream_s3_file():
    """Test the stream_s3_file function with various scenarios."""
    # Mock subprocess.Popen for successful cases
    class MockProcess:
        def __init__(self, stdout_content, stderr_content=b""):
            self.stdout = io.BytesIO(stdout_content)
            self.stderr = io.BytesIO(stderr_content)
            self.returncode = 0
            
        def poll(self):
            return None
            
        def wait(self):
            return 0
    
    # Test regular file streaming
    with patch('subprocess.Popen') as mock_popen:
        test_content = b"test content from s3"
        mock_popen.return_value = MockProcess(test_content)
        
        with stream_s3_file("s3://bucket/test.txt") as stream:
            content = stream.read()
            assert content == test_content
        
        # Verify the correct command was used
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "aws s3 cp s3://bucket/test.txt -" in cmd
    
    # Test gzipped file streaming with decompression
    with patch('subprocess.Popen') as mock_popen:
        test_content = b"test content from s3 gzipped"
        mock_popen.return_value = MockProcess(test_content)
        
        with stream_s3_file("s3://bucket/test.gz", decompress=True) as stream:
            content = stream.read()
            assert content == test_content
        
        # Verify the correct command was used
        cmd = mock_popen.call_args[0][0]
        assert "aws s3 cp s3://bucket/test.gz - | gunzip -c" in cmd
    
    # Test HDF5/H5AD file handling
    with patch('subprocess.Popen') as mock_popen:
        test_content = b"test hdf5 content"
        mock_popen.return_value = MockProcess(test_content)
        
        with stream_s3_file("s3://bucket/test.h5ad", file_format="h5ad") as stream:
            content = stream.read()
            assert content == test_content
            assert isinstance(stream, io.BytesIO)  # Should be BytesIO for HDF5 files
    
    # Test error handling
    with patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = MockProcess(b"", b"Error: NoSuchKey")
        mock_popen.return_value.poll = lambda: 1  # Simulate process failure
        
        with pytest.raises(RuntimeError) as exc_info:
            with stream_s3_file("s3://bucket/nonexistent.txt"):
                pass
        assert "Failed to start S3 stream" in str(exc_info.value)

def test_download_s3_file_to_scratch():
    """Test the download_s3_file_to_scratch function with various scenarios."""
    # Create a temporary directory to simulate scratch space
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock os.environ to return our temp directory
        with patch.dict('os.environ', {'SCRATCH_DIR': temp_dir}, clear=True):
            # Mock uuid.uuid4 to return a consistent value for testing
            with patch('uuid.uuid4', return_value=MagicMock(__str__=lambda _: '1234567890abcdef')):
                # Mock subprocess.run for successful download
                with patch('subprocess.run') as mock_run:
                    # Test successful download
                    test_content = b"test content for h5ad file"
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout="",
                        stderr=""
                    )
                    
                    # Create a temporary file to simulate the downloaded file
                    temp_file_path = os.path.join(temp_dir, "h5ad_12345678_test.h5ad")
                    with open(temp_file_path, 'wb') as temp_file:
                        temp_file.write(test_content)
                    
                    local_path, stats = download_s3_file_to_scratch(
                        "s3://bucket/test.h5ad",
                        file_format="h5ad"
                    )
                    
                    # Verify the file was downloaded
                    assert os.path.exists(local_path)
                    with open(local_path, 'rb') as f:
                        content = f.read()
                        assert content == test_content
                    
                    # Verify stats
                    assert isinstance(stats, dict)
                    assert 'file_size' in stats
                    assert stats['file_size'] == len(test_content)
                    
                    # Verify the correct command was used
                    mock_run.assert_called_once()
                    cmd = mock_run.call_args[0][0]
                    assert "aws s3 cp s3://bucket/test.h5ad" in cmd
                    assert temp_dir in cmd  # Verify temp directory is used
                    
                    # Clean up
                    os.unlink(local_path)
                
                # Test error handling
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=1,
                        stdout="",
                        stderr="Error: NoSuchKey"
                    )
                    
                    local_path, stats = download_s3_file_to_scratch("s3://bucket/nonexistent.h5ad")
                    assert local_path is None
                    assert not stats['success']
                    assert "Failed to download file" in stats['error']
                
                # Test with different file formats
                with patch('subprocess.run') as mock_run:
                    test_content = b"test content for different format"
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout="",
                        stderr=""
                    )
                    
                    # Create a temporary file to simulate the downloaded file
                    temp_file_path = os.path.join(temp_dir, "fastq_12345678_test.fastq")
                    with open(temp_file_path, 'wb') as temp_file:
                        temp_file.write(test_content)
                    
                    local_path, stats = download_s3_file_to_scratch(
                        "s3://bucket/test.fastq",
                        file_format="fastq"
                    )
                    
                    assert os.path.exists(local_path)
                    assert local_path.endswith('.fastq')
                    with open(local_path, 'rb') as f:
                        content = f.read()
                        assert content == test_content
                    
                    # Clean up
                    os.unlink(local_path) 