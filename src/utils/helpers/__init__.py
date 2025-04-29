"""
Utils helpers package.
"""

import os
import logging
import gzip
import subprocess
import shlex
from typing import Optional, BinaryIO

from .file_operations import has_gz_extension, validate_gzip_format

logger = logging.getLogger(__name__)

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

def stream_s3_file(s3_path: str, decompress: Optional[bool] = None) -> BinaryIO:
    """
    Create a stream from an S3 file using AWS CLI.
    
    Args:
        s3_path: S3 path in the format s3://bucket/key
        decompress: Whether to decompress the file. If None, will be determined by file extension.
    
    Returns:
        A file-like object containing the file content
    """
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
    
    return process.stdout

__all__ = [
    'has_gz_extension',
    'validate_gzip_format',
    'stream_s3_file',
    'stream_local_file',
] 