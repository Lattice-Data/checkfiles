"""Core validation functions for file processing."""

import os
import gzip
import logging
import io
import hashlib
import crcmod.predefined
import tempfile
import subprocess
import uuid
from typing import Dict, Any, Optional, BinaryIO, Tuple, Union

from src.tracking.progress import SimpleActivityTracker, ProgressTrackingStream
from src.utils.helpers import has_gz_extension, stream_s3_file, stream_local_file, download_s3_file_to_scratch
from src.validators.base import HashCalculatingStream, GzipHashCalculatingStream
from src.models.validation_record import FileValidationRecord

logger = logging.getLogger(__name__)

def initialize_validator(file_format: str, file_path: str = None) -> Any:
    """Initialize and return the appropriate validator for the given file format.
    
    Args:
        file_format: The file format to validate (e.g., 'fastq')
        file_path: Optional path to the file being validated, used to check file extension
        
    Returns:
        A validator instance for the specified format
        
    Raises:
        ValueError: If the file format is not supported
        ImportError: If the validator module cannot be imported
    """
    logger.debug(f"Initializing validator for {file_format}")
    
    # Special case for HDF5 files with .h5ad extension
    # Use H5adValidator for .h5ad files even if format is specified as hdf5
    if file_format.lower() == "hdf5" and file_path and file_path.lower().endswith('.h5ad'):
        logger.info(f"File {file_path} has .h5ad extension but format 'hdf5'. Using H5adValidator instead of Hdf5Validator.")
        file_format = "h5ad"
    
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
    elif file_format.lower() == "h5ad":
        try:
            from src.validators.h5ad import H5adValidator
            logger.debug("Successfully imported H5adValidator")
            return H5adValidator()
        except ImportError as e:
            logger.error(f"Error importing H5adValidator: {e}")
            print(f"Error importing H5adValidator: {e}")
            try:
                # Try alternative import path
                import sys
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from validators.h5ad import H5adValidator
                logger.debug("Successfully imported H5adValidator using alternative path")
                return H5adValidator()
            except ImportError as e2:
                logger.error(f"Error importing H5adValidator from alternative path: {e2}")
                print(f"Failed to import H5adValidator: {e2}")
                raise ImportError(f"Error importing H5adValidator from all paths: {e}, {e2}")
    elif file_format.lower() == "hdf5":
        try:
            from src.validators.hdf5 import Hdf5Validator
            logger.debug("Successfully imported Hdf5Validator")
            return Hdf5Validator()
        except ImportError as e:
            logger.error(f"Error importing Hdf5Validator: {e}")
            print(f"Error importing Hdf5Validator: {e}")
            try:
                import sys
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from validators.hdf5 import Hdf5Validator
                logger.debug("Successfully imported Hdf5Validator using alternative path")
                return Hdf5Validator()
            except ImportError as e2:
                logger.error(f"Error importing Hdf5Validator from alternative path: {e2}")
                print(f"Failed to import Hdf5Validator: {e2}")
                raise ImportError(f"Error importing Hdf5Validator from all paths: {e}, {e2}")
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

def create_validation_record(result: Dict[str, Any], file_path: str, uuid: str = None, etag: str = None) -> FileValidationRecord:
    """Convert a validation result dictionary to a FileValidationRecord.
    
    Args:
        result: Dictionary with validation results
        file_path: Path to the validated file
        uuid: Optional UUID of the file
        etag: Optional ETag value for concurrency control
        
    Returns:
        A populated FileValidationRecord
    """
    validation_record = FileValidationRecord(file_path, uuid, etag)
    
    # Set validation status
    if 'success' in result:
        validation_record.validation_success = result['success']
    elif 'results' in result and 'valid' in result['results']:
        validation_record.validation_success = result['results']['valid']
    
    # Add stats and metadata as info
    if 'results' in result and 'stats' in result['results']:
        validation_record.update_info(result['results']['stats'])
    
    # Add any platform, read_count, read_length, flowcell_details etc. from results
    if 'results' in result:
        for key in ['platform', 'read_count', 'read_length', 'flowcell_details', 'md5sum', 
                   'sha256', 'crc32c', 'content_md5sum', 'file_size']:
            if key in result['results']:
                validation_record.update_info({key: result['results'][key]})
    
    # Add errors
    if 'error' in result:
        validation_record.update_errors({'validation_error': result['error']})
    elif 'results' in result and 'errors' in result['results']:
        validation_record.update_errors(result['results']['errors'])
    
    return validation_record

def validate_local_file(file_path: str, file_format: str, debug: bool = False, 
                      validator: Optional[Any] = None, 
                      progress_tracker: Optional[SimpleActivityTracker] = None,
                      identifier: str = "", return_record: bool = False, 
                      etag: Optional[str] = None) -> Union[Dict[str, Any], FileValidationRecord]:
    """Validate a local file.
    
    Args:
        file_path: Path to the local file
        file_format: Format of the file (e.g., 'fastq')
        debug: Whether to enable debug output
        validator: Validator instance to use (will be created if None)
        progress_tracker: Activity tracker instance or None if tracking is disabled
        identifier: Optional identifier for the file (e.g., accession number)
        return_record: Whether to return a FileValidationRecord instead of a dictionary
        etag: Optional ETag value for concurrency control
        
    Returns:
        Dictionary with validation results or FileValidationRecord
    """
    try:
        if progress_tracker:
            progress_tracker.init_file(file_path)
            
        track_validation_progress(file_path, progress_tracker, "Initializing")
            
        if validator is None:
            try:
                validator = initialize_validator(file_format, file_path)
                track_validation_progress(file_path, progress_tracker, "Validator created")
            except (ValueError, ImportError) as e:
                raise e
                
        logger.debug(f"Validating local file: {file_path}")
        
        # Initialize validator if not provided
        if not validator:
            try:
                # Pass file_path to help initialize_validator handle .h5ad vs .h5 cases
                validator = initialize_validator(file_format, file_path)
            except (ValueError, ImportError) as e:
                logger.error(f"Failed to initialize validator for {file_format}: {str(e)}")
                error_result = {"file_path": file_path, "success": False, "error": f"Validator initialization failed: {str(e)}"}
                track_validation_progress(file_path, progress_tracker, "Error: Validator init failed", False, error_result)
                return error_result if not return_record else FileValidationRecord.from_dict(error_result)
            
        # --- Handle H5AD format separately (requires file path) ---
        if file_format.lower() == 'h5ad':
            logger.debug(f"Using file-based validation for h5ad: {file_path}")
            track_validation_progress(file_path, progress_tracker, "Validating (file)", None)

            # Calculate hashes for local H5AD/H5 file first
            hash_stats = {}
            local_is_gzipped = has_gz_extension(file_path)
            try:
                track_validation_progress(file_path, progress_tracker, "Calculating hashes")
                with open(file_path, 'rb') as f:
                    # Note: For H5AD/H5, even if the original file is .gz, scanpy reads the uncompressed data.
                    # We calculate hash on the file as it is on disk.
                    hash_stats = calculate_hashes_for_stream(f, local_is_gzipped)
                track_validation_progress(file_path, progress_tracker, "Hashes calculated")
            except Exception as e:
                logger.error(f"Error calculating hashes for {file_path}: {str(e)}", exc_info=True)
                # Don't fail validation just for hash calculation error, but log it.
                error_result = {"file_path": file_path, "success": False, "error": f"Hash calculation failed: {str(e)}"}
                track_validation_progress(file_path, progress_tracker, f"Error: Hash calculation failed", False, error_result)
                # Potentially return error if hashes are strictly required?
                # For now, proceed to validation, hashes will be missing.

            try:
                # Call validate_file directly
                validation_results = validator.validate_file(file_path)

                # Merge calculated hashes into stats
                if "stats" not in validation_results:
                    validation_results["stats"] = {}
                validation_results["stats"].update(hash_stats)

                # Combine with file_path and success flag
                result_dict = {
                    "file_path": file_path,
                    "identifier": identifier if identifier else os.path.basename(file_path),
                    "success": True, # validate_file returns results, success is implied if no exception
                    "results": validation_results
                }
                
                track_validation_progress(file_path, progress_tracker, "Completed", True, validation_results)
                
                if return_record:
                    # Use UUID if available, else create one based on path? (Needs clarification if UUID is needed here)
                    temp_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"file://{file_path}"))
                    return create_validation_record(result_dict, file_path, temp_uuid, etag)
                else:
                    return result_dict
                
            except Exception as e:
                logger.error(f"Error validating {file_path} with validate_file: {str(e)}", exc_info=True)
                error_result = {"file_path": file_path, "success": False, "error": f"Validation failed: {str(e)}"}
                track_validation_progress(file_path, progress_tracker, f"Error: {str(e)}", False, error_result)
                return error_result if not return_record else FileValidationRecord.from_dict(error_result)
            
        # --- Proceed with stream-based validation for other formats ---
        
        # Check if file exists before proceeding
        if not os.path.exists(file_path):
            logger.error(f"Local file not found: {file_path}")
            error_result = {"file_path": file_path, "success": False, "error": "File not found"}
            track_validation_progress(file_path, progress_tracker, "Error: File not found", False, error_result)
            return error_result if not return_record else FileValidationRecord.from_dict(error_result)
        
        is_gzipped = has_gz_extension(file_path)
        logger.debug(f"File is gzipped: {is_gzipped}")
        
        try:
            track_validation_progress(file_path, progress_tracker, "Opening stream", None)
            # Open stream for the local file
            with stream_local_file(file_path) as file_stream:
                logger.debug(f"Successfully opened stream for {file_path}")
                
                # Wrap stream for progress tracking if enabled
                if progress_tracker:
                    file_size = os.path.getsize(file_path)
                    tracked_stream = ProgressTrackingStream(file_stream, file_path, file_size, progress_tracker)
                    stream_to_validate = tracked_stream
                else:
                    stream_to_validate = file_stream
                    
                # Validate the stream content
                track_validation_progress(file_path, progress_tracker, "Validating (stream)", None)
                logger.debug("Calling validator.validate_stream")
                
                # --- THIS IS THE CORE CHANGE: pass is_gzipped only to validate_stream ---
                validation_results = validator.validate_stream(stream_to_validate, is_gzipped=is_gzipped) 
                
                # Combine results
                result_dict = {
                    "file_path": file_path,
                    "results": validation_results,
                    "success": True,
                    "identifier": identifier
                }
                
                track_validation_progress(file_path, progress_tracker, "Completed", True, validation_results)
                
                if return_record:
                    return create_validation_record(result_dict, file_path, identifier, etag)
                else:
                    return result_dict
                
        except Exception as e:
            logger.error(f"Error validating {file_path}: {str(e)}")
            raise RuntimeError(f"Failed to process file: {str(e)}")
            
    except Exception as e:
        error_msg = f"Error validating {file_path}: {str(e)}"
        print(error_msg)
        
        track_validation_progress(file_path, progress_tracker, f"Error: {str(e)}", False, {"error": str(e)})
            
        result = {
            "file_path": file_path,
            "error": error_msg,
            "success": False,
            "identifier": identifier
        }
        
        # Convert to structured record if requested
        if return_record:
            return create_validation_record(result, file_path, identifier, etag)
        
        return result

def download_and_validate_random_access_file(s3_path: str, file_format: str, debug: bool = False,
                                           validator: Optional[Any] = None,
                                           progress_tracker: Optional[SimpleActivityTracker] = None,
                                           identifier: str = "", return_record: bool = False,
                                           etag: Optional[str] = None) -> Union[Dict[str, Any], FileValidationRecord]:
    """
    Download an S3 file that requires random access (like HDF5/H5AD) to the scratch directory and validate it.
    
    Args:
        s3_path: Path to the S3 file (s3://bucket/key)
        file_format: Format of the file (e.g., 'hdf5', 'h5ad')
        debug: Whether to enable debug output
        validator: Validator instance to use (will be created if None)
        progress_tracker: Activity tracker instance or None if tracking is disabled
        identifier: Optional identifier for the file (e.g., accession number)
        return_record: Whether to return a FileValidationRecord instead of a dictionary
        etag: Optional ETag value for concurrency control
        
    Returns:
        Dictionary with validation results or FileValidationRecord
    """
    if progress_tracker:
        progress_tracker.init_file(s3_path)
        progress_tracker.update_progress(s3_path, status="Preparing to download file for validation")
    
    temp_file_path = None
    
    try:
        # Initialize validator if not provided
        if validator is None:
            try:
                validator = initialize_validator(file_format, s3_path)
                if progress_tracker:
                    progress_tracker.update_progress(s3_path, status="Validator initialized")
            except (ValueError, ImportError) as e:
                error_msg = f"Failed to initialize validator: {str(e)}"
                logger.error(error_msg)
                if progress_tracker:
                    progress_tracker.complete_file(s3_path, False, {"error": error_msg})
                
                result_dict = {
                    "file_path": s3_path,
                    "error": error_msg,
                    "success": False,
                    "identifier": identifier
                }
                
                if return_record:
                    return create_validation_record(result_dict, s3_path, identifier, etag)
                return result_dict
        
        # Use the helper function to download the file
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Downloading file from S3")
        
        temp_file_path, download_status = download_s3_file_to_scratch(s3_path, file_format)
        
        if not download_status.get('success', False):
            error_msg = download_status.get('error', 'Unknown download error')
            logger.error(error_msg)
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status=f"Download failed: {error_msg}")
                progress_tracker.complete_file(s3_path, False, {"error": error_msg})
            
            result_dict = {
                "file_path": s3_path,
                "error": error_msg,
                "success": False,
                "identifier": identifier
            }
            
            if return_record:
                return create_validation_record(result_dict, s3_path, identifier, etag)
            return result_dict
        
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status=f"File downloaded successfully to {temp_file_path}, starting validation")
        
        # Calculate S3 object hash separately as we've already downloaded the file
        track_validation_progress(s3_path, progress_tracker, "Calculating hashes from downloaded file")
        hash_stats = {}
        
        # Use a separate file handle for calculating hashes to avoid issues
        with open(temp_file_path, 'rb') as file_stream:
            is_gzipped = has_gz_extension(s3_path)
            hash_stats = calculate_hashes_for_stream(file_stream, is_gzipped)
        
        track_validation_progress(s3_path, progress_tracker, "Hashes calculated")
        
        # For HDF5/H5AD files, use a fresh file stream for validation
        # to ensure the stream is properly closed before validator uses the file
        with open(temp_file_path, 'rb') as validation_stream:
            # We no longer need to wrap the stream for progress here, as validate_file takes the path.
            # if progress_tracker:
            #     validation_stream = ProgressTrackingStream(validation_stream, progress_tracker, update_interval_mb=50)
            #     validation_stream.file_path = s3_path

            # --- CHANGE: Call validate_file instead of validate_stream ---
            logger.debug(f"Calling validate_file for {file_format} on downloaded file: {temp_file_path}")
            validation_results = validator.validate_file(temp_file_path)

        # Combine hash stats with validation results
        validation_results["stats"] = {}
        validation_results["stats"].update(hash_stats)
        
        # Create the final result
        local_result = {
            "file_path": s3_path,  # Use the original S3 path
            "results": validation_results,
            "success": validation_results.get("valid", False),  
            "identifier": identifier
        }
        
        if progress_tracker:
            progress_tracker.complete_file(s3_path, local_result["success"], validation_results)
        
        # Convert to structured record if requested
        if return_record:
            return create_validation_record(local_result, s3_path, identifier, etag)
        
        return local_result
    
    except Exception as e:
        error_msg = f"Error validating {s3_path} (via download): {str(e)}"
        logger.error(error_msg)
        
        if progress_tracker:
            progress_tracker.complete_file(s3_path, False, {"error": error_msg})
        
        result_dict = {
            "file_path": s3_path,
            "error": error_msg,
            "success": False,
            "identifier": identifier
        }
        
        if return_record:
            return create_validation_record(result_dict, s3_path, identifier, etag)
        return result_dict
    
    finally:
        # Clean up the temporary file
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                logger.info(f"Cleaning up temporary file: {temp_file_path}")
                os.remove(temp_file_path)
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")

def validate_s3_file(s3_path: str, file_format: str, debug: bool = False,
                   validator: Optional[Any] = None, 
                   progress_tracker: Optional[SimpleActivityTracker] = None,
                   identifier: str = "", return_record: bool = False,
                   etag: Optional[str] = None) -> Union[Dict[str, Any], FileValidationRecord]:
    """Validate an S3 file using streaming without downloading to disk.
    
    Args:
        s3_path: Path to the S3 file (s3://bucket/key)
        file_format: Format of the file (e.g., 'fastq')
        debug: Whether to enable debug output
        validator: Validator instance to use (will be created if None)
        progress_tracker: Activity tracker instance or None if tracking is disabled
        identifier: Optional identifier for the file (e.g., accession number)
        return_record: Whether to return a FileValidationRecord instead of a dictionary
        etag: Optional ETag value for concurrency control
        
    Returns:
        Dictionary with validation results or FileValidationRecord
    """
    # Special handling for file formats that require random access (HDF5, H5AD)
    if file_format.lower() in ['hdf5', 'h5ad']:
        logger.info(f"File format {file_format} requires random access. Downloading file for validation.")
        return download_and_validate_random_access_file(
            s3_path=s3_path,
            file_format=file_format,
            debug=debug,
            validator=validator,
            progress_tracker=progress_tracker,
            identifier=identifier,
            return_record=return_record,
            etag=etag
        )
    
    # For formats that can be streamed, use the existing streaming approach
    process = None
    
    if progress_tracker:
        progress_tracker.init_file(s3_path)
        progress_tracker.update_progress(s3_path, status="Starting validation")
    
    try:
        if validator is None:
            validator = initialize_validator(file_format, s3_path)
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status="Validator initialized")
            
        print(f"Validating S3 file: {s3_path}")
        
        # Determine if file is gzipped
        is_gzipped = has_gz_extension(s3_path)
        
        # Step 1: Calculate Hashes
        track_validation_progress(s3_path, progress_tracker, "Calculating hashes via S3 stream")
        hash_stats = {}
        # Get first stream for hash calculation (do not decompress here)
        hash_stream = stream_s3_file(s3_path, decompress=False, file_format=file_format)
        try:
            hash_stats = calculate_hashes_for_stream(hash_stream, is_gzipped)
        finally:
            if hasattr(hash_stream, 'close'): hash_stream.close() # Ensure stream resources are cleaned up
        track_validation_progress(s3_path, progress_tracker, "Hashes calculated")
        
        # Step 2: Validate Format
        track_validation_progress(s3_path, progress_tracker, "Running format validation via S3 stream")
        validation_results = {}
        # Get a second stream for the validator (do not decompress here)
        validation_stream_raw = stream_s3_file(s3_path, decompress=False, file_format=file_format)
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
        
        result = {
            "file_path": s3_path,
            "results": validation_results,
            "success": True,
            "identifier": identifier
        }
        
        # Convert to structured record if requested
        if return_record:
            return create_validation_record(result, s3_path, identifier, etag)
        
        return result
        
    except Exception as e:
        error_msg = f"Error validating {s3_path}: {str(e)}"
        logger.error(error_msg)
        
        if progress_tracker:
            progress_tracker.complete_file(s3_path, False, {"error": str(e)})
        
        result = {
            "file_path": s3_path,
            "error": error_msg,
            "success": False,
            "identifier": identifier
        }
        
        # Convert to structured record if requested
        if return_record:
            return create_validation_record(result, s3_path, identifier, etag)
        
        return result 