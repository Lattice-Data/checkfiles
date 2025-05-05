"""Utility functions for file operations and validation."""

import os
import logging
import gzip
import subprocess
import zlib
import shlex
import tempfile
import uuid
from typing import Optional, BinaryIO, IO, Any, Tuple
import io

logger = logging.getLogger(__name__)

def has_gz_extension(filename: str) -> bool:
    """Check if a file has a gzip extension.
    
    Args:
        filename: The filename to check
        
    Returns:
        bool: True if the file has a gzip extension, False otherwise
    """
    return filename.lower().endswith(('.gz', '.gzip'))

def validate_gzip_format(file_path: str) -> dict:
    """
    Validate if a file is properly gzipped by checking magic number and basic header structure.
    Does not read the entire file to avoid performance issues with large files.
    Handles both local files and S3 files.
    
    Args:
        file_path: Path to the file to check. Can be local path or s3:// URL
        
    Returns:
        dict: Empty if valid, contains error message if invalid
    """
    error = {}
    try:
        if file_path.startswith('s3://'):
            # For S3 files, use aws s3 cp to stream just the first few bytes
            cmd = f"aws s3 cp {file_path} - --range 0-1"  # Get first 2 bytes for magic number
            try:
                # Use consistent subprocess pattern with check_output
                magic_number = subprocess.check_output(
                    cmd, 
                    shell=True, 
                    stderr=subprocess.PIPE
                )[:2]
                
                if magic_number != b'\x1f\x8b':
                    error = {'gzip_error': 'File does not have valid gzip magic number'}
                    return error
                
                # Try reading a bit more to verify header structure
                cmd = f"aws s3 cp {file_path} - --range 0-9 | gunzip -c"
                subprocess.check_output(
                    cmd, 
                    shell=True, 
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError as e:
                error = {'gzip_error': f'File has invalid gzip header structure: {e.stderr.decode("utf-8")}'}
        else:
            # For local files, read directly
            with open(file_path, 'rb') as f:
                # Check gzip magic number (1f 8b)
                magic_number = f.read(2)
                if magic_number != b'\x1f\x8b':
                    error = {'gzip_error': 'File does not have valid gzip magic number'}
                    return error
                
                # Verify basic gzip header structure by reading first block
                try:
                    with gzip.open(file_path, 'rb') as gz:
                        # Just read a small amount to verify header structure
                        gz.read(1)
                except (EOFError, zlib.error) as e:
                    error = {'gzip_error': f'File has invalid gzip header structure: {str(e)}'}
                    
    except (IsADirectoryError, FileNotFoundError) as e:
        error = {'gzip_error': str(e)}
    except Exception as e:
        error = {'gzip_error': f'Unexpected error checking gzip format: {str(e)}'}
        
    return error

def download_s3_file_to_scratch(s3_path: str, file_format: str = None) -> Tuple[str, dict]:
    """
    Download a file from S3 to the scratch directory.
    
    This is particularly useful for file formats that require random access,
    such as HDF5 and H5AD files, which cannot be validated by streaming.
    
    Args:
        s3_path: S3 path in the format s3://bucket/key
        file_format: Optional file format for specialized naming
    
    Returns:
        Tuple containing (local_file_path, status_dict) where status_dict
        contains information about the download operation
    """
    status = {}
    
    if not s3_path.startswith("s3://"):
        error_msg = f"Invalid S3 path: {s3_path}. Path must start with s3://"
        logger.error(error_msg)
        status['success'] = False
        status['error'] = error_msg
        return None, status
    
    # Use the /mnt/scratch directory if available, otherwise use system temp directory
    scratch_dir = os.environ.get('SCRATCH_DIR', '/mnt/scratch')
    if not os.path.exists(scratch_dir):
        try:
            logger.info(f"Creating scratch directory: {scratch_dir}")
            os.makedirs(scratch_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            scratch_dir = tempfile.gettempdir()
            logger.warning(f"Could not create or access scratch directory. Using system temp: {scratch_dir}")
    
    # Create a unique filename in the scratch directory
    file_name = os.path.basename(s3_path)
    prefix = ""
    if file_format:
        prefix = f"{file_format.lower()}_"
    unique_suffix = str(uuid.uuid4())[:8]
    temp_file_path = os.path.join(scratch_dir, f"{prefix}{unique_suffix}_{file_name}")
    
    try:
        # Download the file using AWS CLI
        cmd = f"aws s3 cp {s3_path} {temp_file_path}"
        logger.info(f"Downloading file: {cmd}")
        
        # Check if we need to create the parent directory
        parent_dir = os.path.dirname(temp_file_path)
        if not os.path.exists(parent_dir):
            try:
                logger.info(f"Creating parent directory: {parent_dir}")
                os.makedirs(parent_dir, exist_ok=True)
            except (PermissionError, OSError) as e:
                error_msg = f"Failed to create parent directory {parent_dir}: {str(e)}"
                logger.error(error_msg)
                status['success'] = False
                status['error'] = error_msg
                return None, status
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = f"Failed to download file from {s3_path}: {result.stderr}"
            logger.error(error_msg)
            status['success'] = False
            status['error'] = error_msg
            return None, status
        
        # Check if file was downloaded successfully
        if not os.path.exists(temp_file_path):
            error_msg = f"File was not downloaded to {temp_file_path}"
            logger.error(error_msg)
            status['success'] = False
            status['error'] = error_msg
            return None, status
        
        # Check file size
        file_size = os.path.getsize(temp_file_path)
        if file_size == 0:
            error_msg = f"Downloaded file is empty (0 bytes): {temp_file_path}"
            logger.error(error_msg)
            status['success'] = False
            status['error'] = error_msg
            # Delete the empty file
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
            return None, status
            
        # Log success information
        logger.info(f"Successfully downloaded {s3_path} to {temp_file_path} ({file_size} bytes)")
        status['success'] = True
        status['local_path'] = temp_file_path
        status['original_s3_path'] = s3_path
        status['file_size'] = file_size
        return temp_file_path, status
        
    except Exception as e:
        error_msg = f"Error downloading file from {s3_path}: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        status['success'] = False
        status['error'] = error_msg
        return None, status

def stream_local_file(file_path: str, decompress: Optional[bool] = None) -> BinaryIO:
    """
    Create a stream from a local file using subprocess if decompression is needed,
    otherwise open the file directly.
    
    This avoids loading the entire file into memory, especially for large gzipped files.
    
    Args:
        file_path: Path to the local file
        decompress: Whether to decompress the file. If None, will be determined by file extension.
    
    Returns:
        A file-like object containing the file content
    """
    # Determine if we should decompress based on file extension if not specified
    if decompress is None:
        decompress = has_gz_extension(file_path)
    
    # Escape the file path for shell safety
    file_path_escaped = shlex.quote(file_path)
    
    if decompress:
        # Use gunzip to decompress the file via subprocess
        cmd = f"cat {file_path_escaped} | gunzip -c"
        
        logger.debug(f"Using streaming decompression for {file_path} with command: {cmd}")
        
        # Start the subprocess
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1048576  # 1MB buffer
        )
        
        # Check if process started successfully
        if process.poll() is not None:
            stderr = process.stderr.read().decode('utf-8')
            logger.error(f"Failed to start decompression stream: {stderr}")
            raise RuntimeError(f"Failed to start decompression stream: {stderr}")
        
        logger.debug(f"Streaming decompression process started successfully for {file_path}")
        return process.stdout
    else:
        # For non-compressed files, just open the file directly
        # This is more efficient than using a subprocess
        logger.debug(f"Opening non-compressed file directly: {file_path}")
        return open(file_path, 'rb')

def stream_s3_file(s3_path: str, decompress: Optional[bool] = None, file_format: Optional[str] = None) -> BinaryIO:
    """
    Create a stream from an S3 file using AWS CLI.
    
    Args:
        s3_path: S3 path in the format s3://bucket/key
        decompress: Whether to decompress the file. If None, will be determined by file extension.
        file_format: Optional file format to handle format-specific streaming requirements
    
    Returns:
        A file-like object containing the file content
    """
    # Warn about non-seekable streams for HDF5/H5AD files
    if file_format and file_format.lower() in ['hdf5', 'h5ad']:
        logger.warning(f"Using stream_s3_file with {file_format} format. This format requires random access and should use download_s3_file_to_scratch instead.")
    
    # Determine if we should decompress based on file extension if not specified
    if decompress is None:
        decompress = has_gz_extension(s3_path)
    
    # Escape the s3 path for shell safety
    s3_path_escaped = shlex.quote(s3_path)
    
    if decompress:
        cmd = f"aws s3 cp {s3_path_escaped} - | gunzip -c"
    else:
        cmd = f"aws s3 cp {s3_path_escaped} -"
    
    # Start the subprocess
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1048576  # 1MB buffer
    )
    
    # Check if process started successfully
    if process.poll() is not None:
        stderr = process.stderr.read().decode('utf-8')
        raise RuntimeError(f"Failed to start S3 stream: {stderr}")
    
    # Create a BytesIO object that's more compatible with most validation operations
    # This is especially important for small files that can fit in memory
    if file_format and file_format.lower() in ['hdf5', 'h5ad']:
        logger.info("For HDF5/H5AD files, reading entire content to BytesIO for better compatibility")
        content = process.stdout.read()
        process.wait()  # Make sure the process completes
        return io.BytesIO(content)
    else:
        # For other formats, return the raw stream
        return process.stdout 