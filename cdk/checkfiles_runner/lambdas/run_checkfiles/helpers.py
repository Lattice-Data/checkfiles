"""
Helper utilities for file operations and S3 access, bundled for Lambda use.

This module provides standalone versions of the helper functions that are
used by the checkfiles utility, avoiding import path issues in Lambda.
"""

import os
import io
import logging
import gzip
import zlib
import boto3
from typing import Dict, BinaryIO, Optional

logger = logging.getLogger(__name__)

def has_gz_extension(filename: str) -> bool:
    """
    Check if a filename has a .gz extension.
    
    Args:
        filename: File name to check
        
    Returns:
        True if the file has a .gz extension, False otherwise
    """
    return filename.lower().endswith(('.gz', '.gzip'))

def validate_gzip_format(file_path: str) -> Dict:
    """
    Validate if a file is properly gzipped by checking magic number and basic header structure.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        Dict: Empty if valid, contains error message if invalid
    """
    error = {}
    try:
        if file_path.startswith('s3://'):
            # Parse S3 path
            parts = file_path[5:].split('/', 1)
            bucket, key = parts
            s3_client = boto3.client('s3')
            
            # Get just the first few bytes to check the magic number
            response = s3_client.get_object(
                Bucket=bucket,
                Key=key,
                Range='bytes=0-1'
            )
            magic_number = response['Body'].read()
            
            if magic_number != b'\x1f\x8b':
                error = {'gzip_error': 'File does not have valid gzip magic number'}
                return error
            
            # Try to read and decompress a small part of the file
            try:
                response = s3_client.get_object(
                    Bucket=bucket,
                    Key=key,
                    Range='bytes=0-100'
                )
                data = response['Body'].read()
                gzip.decompress(data)
            except Exception as e:
                error = {'gzip_error': f'File has invalid gzip structure: {str(e)}'}
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
    except Exception as e:
        error = {'gzip_error': f'Unexpected error checking gzip format: {str(e)}'}
        
    return error

def stream_local_file(file_path: str, decompress: Optional[bool] = False) -> BinaryIO:
    """
    Create a stream from a local file.
    
    Args:
        file_path: Path to the local file
        decompress: Whether to decompress the file
        
    Returns:
        Binary IO stream of the file contents
    """
    # Check if file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Open file in binary mode
    with open(file_path, 'rb') as f:
        # Read all data into memory
        data = f.read()
    
    # Create BytesIO object
    stream = io.BytesIO(data)
    
    # Decompress if needed
    if decompress:
        try:
            # Reset stream position
            stream.seek(0)
            # Create gzip stream
            gzip_stream = gzip.GzipFile(fileobj=stream, mode='rb')
            # Read all data from gzip stream
            decompressed = io.BytesIO(gzip_stream.read())
            # Reset position and return
            decompressed.seek(0)
            return decompressed
        except Exception as e:
            raise ValueError(f"Error decompressing file: {e}")
    
    # Reset stream position and return
    stream.seek(0)
    return stream

def stream_s3_file(s3_path: str, decompress: Optional[bool] = False) -> BinaryIO:
    """
    Stream a file from S3 as a binary stream.
    
    Args:
        s3_path: S3 path in the format s3://bucket/key
        decompress: Whether to decompress the stream (for gzipped files)
        
    Returns:
        Binary IO stream of the file contents
    """
    # Parse S3 path
    if not s3_path.startswith('s3://'):
        raise ValueError(f"Invalid S3 path: {s3_path}. Must start with s3://")
    
    parts = s3_path[5:].split('/', 1)  # Remove 's3://' prefix and split on first '/'
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 path format: {s3_path}. Expected s3://bucket/key")
    
    bucket, key = parts
    
    # Get the object from S3
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=bucket, Key=key)
    
    # Read the data into a BytesIO object
    data = response['Body'].read()
    stream = io.BytesIO(data)
    
    # Decompress if needed
    if decompress:
        # Reset stream position
        stream.seek(0)
        # Create a gzip stream
        gzip_stream = gzip.GzipFile(fileobj=stream, mode='rb')
        # Read all data from gzip stream into a new BytesIO object
        decompressed = io.BytesIO(gzip_stream.read())
        # Reset position and return
        decompressed.seek(0)
        return decompressed
    
    # Reset stream position and return
    stream.seek(0)
    return stream 