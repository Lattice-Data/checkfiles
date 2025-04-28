"""Core validation functions for file processing."""

import os
import gzip
import logging
import io
import hashlib
import crcmod.predefined
import tempfile
import subprocess
from typing import Dict, Any, Optional, BinaryIO

from src.tracking.progress import SimpleActivityTracker, ProgressTrackingStream
from src.utils.helpers import has_gz_extension, stream_s3_file

logger = logging.getLogger(__name__)

def initialize_validator(file_format: str) -> Any:
    """Initialize and return the appropriate validator for the given file format.
    
    Args:
        file_format: The file format to validate (e.g., 'fastq')
        
    Returns:
        A validator instance for the specified format
        
    Raises:
        ValueError: If the file format is not supported
        ImportError: If the validator module cannot be imported
    """
    logger.debug(f"Initializing validator for {file_format}")
    
    if file_format.lower() == "fastq":
        try:
            from src.validators.fastq import FastqValidator
            logger.debug("Successfully imported FastqValidator")
            return FastqValidator()
        except ImportError as e:
            logger.error(f"Error importing FastqValidator: {e}")
            print(f"Error importing FastqValidator: {e}")
            print("Using pure Python implementation - no Rust required")
            try:
                # Try alternative import path
                import sys
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from validators.fastq import FastqValidator
                logger.debug("Successfully imported FastqValidator using alternative path")
                return FastqValidator()
            except ImportError as e2:
                logger.error(f"Error importing FastqValidator from alternative path: {e2}")
                print(f"Failed to import FastqValidator: {e2}")
                raise ImportError(f"Error importing FastqValidator from all paths: {e}, {e2}")
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

def track_validation_progress(file_path: str, progress_tracker: Optional[SimpleActivityTracker], 
                            status_message: Optional[str], success: Optional[bool] = None, 
                            results: Optional[Dict[str, Any]] = None) -> None:
    """Helper function to handle progress tracking for file validation.
    
    Args:
        file_path: Path to the file being processed
        progress_tracker: Activity tracker instance or None if tracking is disabled
        status_message: Status message to record
        success: Whether the validation was successful (None if not complete)
        results: Validation results (required if success is not None)
    """
    if not progress_tracker:
        return
        
    if status_message:
        progress_tracker.update_progress(file_path, status=status_message)
        
    if success is not None and results is not None:
        progress_tracker.complete_file(file_path, success, results)

def validate_local_file(file_path: str, file_format: str, debug: bool = False, 
                      validator: Optional[Any] = None, 
                      progress_tracker: Optional[SimpleActivityTracker] = None) -> Dict[str, Any]:
    """Validate a local file.
    
    Args:
        file_path: Path to the local file
        file_format: Format of the file (e.g., 'fastq')
        debug: Whether to enable debug output
        validator: Validator instance to use (will be created if None)
        progress_tracker: Activity tracker instance or None if tracking is disabled
        
    Returns:
        Dictionary with validation results
    """
    try:
        if progress_tracker:
            progress_tracker.init_file(file_path)
            
        track_validation_progress(file_path, progress_tracker, "Initializing")
            
        if validator is None:
            try:
                validator = initialize_validator(file_format)
                track_validation_progress(file_path, progress_tracker, "Validator created")
            except (ValueError, ImportError) as e:
                raise e
                
        print(f"Validating local file: {file_path}")
        
        track_validation_progress(file_path, progress_tracker, "Reading file")
        
        # Check if local file is gzipped
        if has_gz_extension(file_path):
            track_validation_progress(file_path, progress_tracker, "Decompressing")
                
            with gzip.open(file_path, 'rb') as f:
                track_validation_progress(file_path, progress_tracker, "Running validation")
                results = validator.validate_stream(f)
        else:
            track_validation_progress(file_path, progress_tracker, "Running validation")
            results = validator.validate_file(file_path)
            
        track_validation_progress(file_path, progress_tracker, "Validation complete", True, results)
            
        return {
            "file_path": file_path,
            "results": results,
            "success": True
        }
        
    except Exception as e:
        error_msg = f"Error validating {file_path}: {str(e)}"
        print(error_msg)
        
        track_validation_progress(file_path, progress_tracker, f"Error: {str(e)}", False, {"error": str(e)})
            
        return {
            "file_path": file_path,
            "error": error_msg,
            "success": False
        }

def validate_s3_file(s3_path: str, file_format: str, debug: bool = False,
                   validator: Optional[Any] = None, 
                   progress_tracker: Optional[SimpleActivityTracker] = None) -> Dict[str, Any]:
    """Validate an S3 file using streaming without downloading to disk.
    
    Args:
        s3_path: Path to the S3 file (s3://bucket/key)
        file_format: Format of the file (e.g., 'fastq')
        debug: Whether to enable debug output
        validator: Validator instance to use (will be created if None)
        progress_tracker: Activity tracker instance or None if tracking is disabled
        
    Returns:
        Dictionary with validation results
    """
    process = None
    
    if progress_tracker:
        progress_tracker.init_file(s3_path)
        progress_tracker.update_progress(s3_path, status="Starting validation")
    
    try:
        if validator is None:
            validator = initialize_validator(file_format)
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status="Validator initialized")
            
        print(f"Validating S3 file: {s3_path}")
        
        track_validation_progress(s3_path, progress_tracker, "Setting up stream")
        
        # Stream from S3
        stream = stream_s3_file(s3_path, decompress=has_gz_extension(s3_path))
        
        track_validation_progress(s3_path, progress_tracker, "Stream established")
        
        # Wrap the stream with progress tracking
        tracking_stream = ProgressTrackingStream(stream, progress_tracker)
        # Store the file path for progress updates
        if progress_tracker:
            tracking_stream.file_path = s3_path
        
        # Run validation directly on the streaming data
        logger.debug("Starting validation")
        results = validator.validate_stream(tracking_stream)
        logger.debug("Validation completed")
        
        # We don't calculate hashes in streaming mode to avoid reading the file twice
        # If hash values are needed, they should be calculated separately
        
        if progress_tracker:
            progress_tracker.complete_file(s3_path, True, results)
        
        return {
            "file_path": s3_path,
            "results": results,
            "success": True
        }
        
    except Exception as e:
        error_msg = f"Error validating {s3_path}: {str(e)}"
        logger.error(error_msg)
        
        if progress_tracker:
            progress_tracker.complete_file(s3_path, False, {"error": str(e)})
        
        return {
            "file_path": s3_path,
            "error": error_msg,
            "success": False
        } 