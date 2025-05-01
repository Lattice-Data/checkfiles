"""Core validation functions for file processing."""

import os
import gzip
import logging
import io
import hashlib
import crcmod.predefined
import tempfile
import subprocess
from typing import Dict, Any, Optional, BinaryIO, Tuple

from src.tracking.progress import SimpleActivityTracker, ProgressTrackingStream
from src.utils.helpers import has_gz_extension, stream_s3_file, stream_local_file
from src.validators.base import HashCalculatingStream, GzipHashCalculatingStream

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

def calculate_hashes_for_stream(stream: BinaryIO, is_gzipped: bool) -> Dict[str, Any]:
    """Calculate standard hashes (md5, sha256, crc32c, content_md5sum if gzipped) for a stream.
    
    This function consumes the stream.
    
    Args:
        stream: The input stream to read from.
        is_gzipped: Whether the stream contains gzipped data.
        
    Returns:
        Dictionary containing hash values ('md5sum', 'sha256', 'crc32c', 
        'content_md5sum', 'file_size', 'content_size').
    """
    logger.debug(f"Calculating hashes, is_gzipped={is_gzipped}")
    
    # Initialize hash calculators (using BaseValidator's logic for consistency)
    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()
    crc32c_func = crcmod.predefined.Crc('crc-32c')
    
    hash_calculators = [
        ('md5sum', md5_hash),
        ('sha256', sha256_hash),
        ('crc32c', crc32c_func)
    ]
    
    if is_gzipped:
        hash_stream = GzipHashCalculatingStream(stream, hash_calculators)
    else:
        hash_stream = HashCalculatingStream(stream, hash_calculators)
        
    # Read the entire stream to calculate hashes
    while hash_stream.read(io.DEFAULT_BUFFER_SIZE):
        pass
        
    # Get hash values (using BaseValidator's logic)
    stats = {}
    stats['file_size'] = hash_stream.get_total_bytes()
    hash_digests = hash_stream.get_hash_digests()
    for hash_name, digest in hash_digests.items():
        stats[hash_name] = digest.lower() if hash_name == 'crc32c' else digest
        
    if isinstance(hash_stream, GzipHashCalculatingStream):
        stats['content_md5sum'] = hash_stream.get_content_md5sum()
        stats['content_size'] = hash_stream.get_content_size()
        
    logger.debug(f"Hash calculation complete: {list(stats.keys())}")
    return stats

def validate_local_file(file_path: str, file_format: str, debug: bool = False, 
                      validator: Optional[Any] = None, 
                      progress_tracker: Optional[SimpleActivityTracker] = None,
                      identifier: str = "") -> Dict[str, Any]:
    """Validate a local file.
    
    Args:
        file_path: Path to the local file
        file_format: Format of the file (e.g., 'fastq')
        debug: Whether to enable debug output
        validator: Validator instance to use (will be created if None)
        progress_tracker: Activity tracker instance or None if tracking is disabled
        identifier: Optional identifier for the file (e.g., accession number)
        
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
        
        # Check if local file is gzipped
        is_gzipped = has_gz_extension(file_path)
        
        try:
            # Step 1: Calculate Hashes
            track_validation_progress(file_path, progress_tracker, "Calculating hashes")
            hash_stats = {}
            # Open first stream for hash calculation
            with open(file_path, 'rb') as file_stream:
                hash_stats = calculate_hashes_for_stream(file_stream, is_gzipped)
            track_validation_progress(file_path, progress_tracker, "Hashes calculated")

            # Step 2: Validate Format
            track_validation_progress(file_path, progress_tracker, "Running format validation")
            validation_results = {}
            # Open a second stream for the validator
            with open(file_path, 'rb') as validation_stream:
                if progress_tracker:
                    # Wrap the validation stream for progress tracking
                    tracking_stream = ProgressTrackingStream(validation_stream, progress_tracker, update_interval_mb=100)
                    tracking_stream.file_path = file_path
                    stream = tracking_stream
                else:
                    stream = validation_stream
                    
                # The validator now only performs format validation
                # It should return format-specific results (valid, errors, warnings, other stats)
                validation_results = validator.validate_stream(stream, is_gzipped=is_gzipped)
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise RuntimeError(f"Failed to process file: {str(e)}")
            
        # Combine results: validation details + hash stats
        # Ensure 'stats' dictionary exists in validation_results
        if 'stats' not in validation_results:
            validation_results['stats'] = {}
        validation_results['stats'].update(hash_stats) # Add hashes to the stats dict
        
        track_validation_progress(file_path, progress_tracker, "Validation complete", True, validation_results)
            
        return {
            "file_path": file_path,
            "results": validation_results, # Return combined results
            "success": True,
            "identifier": identifier
        }
        
    except Exception as e:
        error_msg = f"Error validating {file_path}: {str(e)}"
        print(error_msg)
        
        track_validation_progress(file_path, progress_tracker, f"Error: {str(e)}", False, {"error": str(e)})
            
        return {
            "file_path": file_path,
            "error": error_msg,
            "success": False,
            "identifier": identifier
        }

def validate_s3_file(s3_path: str, file_format: str, debug: bool = False,
                   validator: Optional[Any] = None, 
                   progress_tracker: Optional[SimpleActivityTracker] = None,
                   identifier: str = "") -> Dict[str, Any]:
    """Validate an S3 file using streaming without downloading to disk.
    
    Args:
        s3_path: Path to the S3 file (s3://bucket/key)
        file_format: Format of the file (e.g., 'fastq')
        debug: Whether to enable debug output
        validator: Validator instance to use (will be created if None)
        progress_tracker: Activity tracker instance or None if tracking is disabled
        identifier: Optional identifier for the file (e.g., accession number)
        
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
        
        # Determine if file is gzipped
        is_gzipped = has_gz_extension(s3_path)
        
        # Step 1: Calculate Hashes
        track_validation_progress(s3_path, progress_tracker, "Calculating hashes via S3 stream")
        hash_stats = {}
        # Get first stream for hash calculation (do not decompress here)
        hash_stream = stream_s3_file(s3_path, decompress=False)
        try:
            hash_stats = calculate_hashes_for_stream(hash_stream, is_gzipped)
        finally:
            if hasattr(hash_stream, 'close'): hash_stream.close() # Ensure stream resources are cleaned up
        track_validation_progress(s3_path, progress_tracker, "Hashes calculated")
        
        # Step 2: Validate Format
        track_validation_progress(s3_path, progress_tracker, "Running format validation via S3 stream")
        validation_results = {}
        # Get a second stream for the validator (do not decompress here)
        validation_stream_raw = stream_s3_file(s3_path, decompress=False)
        try:
            if progress_tracker:
                tracking_stream = ProgressTrackingStream(validation_stream_raw, progress_tracker, update_interval_mb=100)
                tracking_stream.file_path = s3_path
                stream_for_validator = tracking_stream
            else:
                stream_for_validator = validation_stream_raw
                
            validation_results = validator.validate_stream(stream_for_validator, is_gzipped=is_gzipped)
        finally:
             if hasattr(validation_stream_raw, 'close'): validation_stream_raw.close() # Ensure stream resources are cleaned up
             
        logger.debug("Validation completed")
        
        if progress_tracker:
            progress_tracker.complete_file(s3_path, True, validation_results)
        
        # Combine results
        validation_results['stats'] = {**validation_results.get('stats', {}), **hash_stats}
        
        return {
            "file_path": s3_path,
            "results": validation_results,
            "success": True,
            "identifier": identifier
        }
        
    except Exception as e:
        error_msg = f"Error validating {s3_path}: {str(e)}"
        logger.error(error_msg)
        
        if progress_tracker:
            progress_tracker.complete_file(s3_path, False, {"error": str(e)})
        
        return {
            "file_path": s3_path,
            "error": error_msg,
            "success": False,
            "identifier": identifier
        } 