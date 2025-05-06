"""
Helper utilities for file operations and S3 access.

This module consolidates file operation helpers from various submodules
to provide a consistent interface.
"""

import os
import logging
import gzip
import subprocess
import zlib
import shlex
import tempfile
import uuid
from typing import Optional, BinaryIO, IO, Any, Tuple

# Import specific functions from submodules 
from src.utils.helpers.file_operations import has_gz_extension, validate_gzip_format
from src.utils.helpers.streams import stream_local_file, stream_s3_file, download_s3_file_to_scratch

logger = logging.getLogger(__name__)

# Re-export the functions
__all__ = ['has_gz_extension', 'validate_gzip_format', 'stream_local_file', 'stream_s3_file', 'download_s3_file_to_scratch'] 