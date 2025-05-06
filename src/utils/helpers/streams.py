"""
Stream handling utilities for file operations.
This module provides a simplified interface to the file operations module.
"""

from src.utils.helpers.file_operations import (
    stream_local_file,
    stream_s3_file,
    download_s3_file_to_scratch
)

# Re-export the functions for backward compatibility
__all__ = ['stream_local_file', 'stream_s3_file', 'download_s3_file_to_scratch'] 