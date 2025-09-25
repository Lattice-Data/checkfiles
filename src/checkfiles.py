#!/usr/bin/env python3
"""
Checkfiles utility - validates file formats like FASTQ.
Handles files from local paths, S3, or a backend API query.
"""

import sys
import os
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import logging
import threading
from typing import List, Dict, Any, Tuple, Optional, Union
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter  # noqa: F401
from urllib3.util.retry import Retry  # noqa: F401
import json
import tempfile
import traceback
import time

# AWS-specific imports (only used in AWS environment)
try:
    import boto3
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

# Configure logging
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'checkfiles_debug.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='w'
)
logger = logging.getLogger(__name__)
logger.debug(f"Logging to: {log_file}")

# Try to fix import path
try:
    # Add potential module locations to path
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    potential_paths = [
        f"/usr/local/lib/python{python_version}/dist-packages",
        f"/usr/local/lib/python{python_version}/site-packages",
        "/opt/checkfiles/python",
        os.path.join(os.getcwd(), "src")
    ]
    
    for path in potential_paths:
        if path not in sys.path and os.path.exists(path):
            logger.debug(f"Adding {path} to sys.path")
            sys.path.insert(0, path)
except ImportError as e:
    logger.debug(f"Failed to set up Python paths: {e}")

# Import internal modules
try:
    from src.models.validation_record import FileValidationRecord
    from src.cli.parser import parse_arguments
    from src.backend.patch import fetch_etag_for_uuid, compare_with_db, patch_file
    from src.core.validation import (
        validate_s3_file as core_validate_s3_file,
        create_validation_record,
        SimpleActivityTracker,
        initialize_validator,
        validate_local_file
    )
    from src.tracking.progress import SimpleActivityTracker
    from src.utils.helpers import has_gz_extension, validate_gzip_format
    from src.path_translator import resolve_path, is_s3_uri
    from src.worker.patch_worker import patching_worker, check_credentials_expired
    from src.utils.s3_utils import set_s3_tags
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    print(f"Error: Failed to import required modules: {e}")
    # Try to find the module in alternative locations
    for module_name in ["src.cli.parser", "src.core.validation", "src.tracking.progress", 
                       "src.utils.helpers", "src.path_translator"]:
        try:
            __import__(module_name)
            logger.debug(f"Successfully imported {module_name}")
        except ImportError as e:
            logger.error(f"Could not import {module_name}: {e}")

# Define a helper function for writing to logs that doesn't depend on a global lock
def write_result_to_progress_log(result: FileValidationRecord) -> None:
    """Write a validation result to the validation_progress.log file.
    
    Args:
        result: The validation result record
    """
    log_dir = os.getenv('CHECKFILES_LOG_DIR', os.getcwd())
    os.makedirs(log_dir, exist_ok=True)
    progress_log_path = os.path.join(log_dir, 'validation_progress.log')
    print(f"Writing result to {progress_log_path}")
    
    # Extract fields from FileValidationRecord
    file_path = result.file_path
    success = result.validation_success
    info = result.info
    errors = result.errors
    identifier = result.uuid or os.path.basename(file_path)
    
    # Use file_path for URI
    uri = file_path

        if success:
        # Prefer the exact patch payload if present (recorded at patch time)
        json_patch = {}
        if hasattr(result, 'patch_payload') and isinstance(result.patch_payload, dict):
            json_patch = result.patch_payload
        else:
            # Fallback: build a minimal display patch from info (legacy behavior)
            patch_keys = [
                'file_size',
                'md5sum',
                'sha256',
                'crc32c',
                'content_md5sum',
                'observation_count',
                'genomes',
                'feature_counts',
                'is_hdf5',
                'read_count',
                'read_length',
                'platform',
                'flowcell_details'
            ]
            for key in patch_keys:
                if key in info:
                    json_patch[key] = info[key]
            # Do not force add validated here; actual patch payload will contain it if applicable

        # Ensure dicts are properly JSON formatted for the log line
        errors_str = json.dumps(errors)
        stats_str = json.dumps(info)
        patch_str = json.dumps(json_patch)

        # Determine patch statuses if available on result
        lattice_status = 'success' if getattr(result, 'patched', False) else 'failed'
        s3_status = 'success' if getattr(result, 's3_tagged', False) else 'failed'
        log_line = f"{identifier}\t{uri}\t{errors_str}\t{stats_str}\t{patch_str}\t{lattice_status}\t{s3_status}"
    else:
        # For failed validations, ensure we capture all error information
        error_dict = {}
        if errors:
            # If we have specific errors, use them
            error_dict = errors
        else:
            # If no specific errors, use a generic error message
            error_dict = {'validation_error': 'Validation failed'}
            
        # Create empty stats and patch for failed validation
        empty_dict = {}
        
        # Ensure all dicts are properly JSON formatted
        error_dict_str = json.dumps(error_dict)
        empty_dict_str = json.dumps(empty_dict)
        
        lattice_status = 'failed' if not getattr(result, 'patched', False) else 'success'
        s3_status = 'failed' if not getattr(result, 's3_tagged', False) else 'success'
        log_line = f"{identifier}\t{uri}\t{error_dict_str}\t{empty_dict_str}\t{empty_dict_str}\t{lattice_status}\t{s3_status}"
    
    # Use file locking to ensure atomic writes
    try:
        # Check if the file exists and has the header
        file_exists = os.path.exists(progress_log_path)
        
        # If file doesn't exist or is empty, write the header first
        mode = 'a'  # Append by default
        if not file_exists or os.path.getsize(progress_log_path) == 0:
            mode = 'w'  # Write mode if file doesn't exist or is empty
            
        with open(progress_log_path, mode) as f:
            if mode == 'w':
                f.write("identifier\turi\terrors\tresults\tjson_patch\tLattice patched?\tS3 tag patched?\n")
            f.write(f"{log_line}\n")
            f.flush()
            os.fsync(f.fileno())  # Ensure data is written to disk
    except Exception as e:
        logger.error(f"Error writing to progress log: {e}")

def fetch_files_from_backend(backend_uri: str, query: str, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """Fetch files from backend using query and backend_uri.
    
    Args:
        backend_uri: Base URI of the backend service
        query: Query string for filtering files
        
    Returns:
        List of file objects to validate
    """
    logger.info(f"Fetching files from backend using query: {query}")
    print("fetching file objects from backend")
    # Get authentication credentials from environment variables
    portal_key = os.getenv('PORTAL_KEY')
    portal_secret_key = os.getenv('PORTAL_SECRET_KEY')
    if not portal_key or not portal_secret_key:
        logger.error("Missing authentication credentials. Please set PORTAL_KEY and PORTAL_SECRET_KEY environment variables.")
        return []
    
    # Set up authentication
    auth = (portal_key, portal_secret_key)
    
    # Construct the full query URL
    query_url = urljoin(backend_uri, query.replace('report', 'search') + '&format=json&limit=all')
    logger.debug(f"Querying backend search: {query_url}")

    # Prepare HTTP client: use provided session if any (production path), else fall back to requests.get (test path)
    if session is None:
        # Do not create a session in tests; tests patch requests.get
        def http_get(url, **kwargs):
            return requests.get(url, **kwargs)
    else:
        # Ensure retries and connection behavior are configured by the caller
        def http_get(url, **kwargs):
            return session.get(url, **kwargs)
    
    try:
        # Make the request to the backend
        query_kwargs = {"auth": auth}
        if session is not None:
            query_kwargs["timeout"] = 15
        response = http_get(query_url, **query_kwargs)
        response.raise_for_status()
        
        # Extract accessions from the response
        graph_items = response.json().get('@graph', [])
        accessions = [x.get('accession') for x in graph_items if x.get('accession')]
        logger.info(f"Found {len(graph_items)} items in search; {len(accessions)} with accessions")
        logger.debug(f"First 5 accessions: {accessions[:5]}")
        
        # Fetch full file objects for each accession
        files_to_validate = []
        total_items = len(graph_items)
        for idx, item in enumerate(graph_items, start=1):
            # Prefer canonical @id to avoid redirects
            item_id = item.get('@id')  # e.g., '/raw-sequence-files/LATDF702BUN/'
            acc = item.get('accession', '')
            if item_id:
                item_path = f"{item_id}?frame=object" if not item_id.endswith('?frame=object') else item_id
                item_url = urljoin(backend_uri, item_path)
                target_label = item_id
            else:
                # Fallback to accession path (may redirect)
                item_url = urljoin(backend_uri, f"{acc}/?frame=object")
                target_label = acc
                logger.debug(f"@id missing for accession {acc}; using accession URL which may redirect")

            logger.debug(f"[{idx}/{total_items}] Fetching file object: {target_label} -> {item_url}")

            try:
                item_kwargs = {"auth": auth}
                if session is not None:
                    item_kwargs["timeout"] = 15
                file_response = http_get(item_url, **item_kwargs)
                if not file_response.ok:
                    logger.error(f"Failed to fetch file object for {target_label}: HTTP {file_response.status_code}")
                    continue

                file_json = file_response.json()

                # Check if file should be validated
                if file_json.get('no_file_available'):
                    logger.info(f"Skipping {acc or file_json.get('uuid','unknown')}: marked as no_file_available")
                    continue

                if not file_json.get('s3_uri'):
                    logger.info(f"Skipping {acc or file_json.get('uuid','unknown')}: no URI available")
                    continue

                files_to_validate.append(file_json)
            except requests.HTTPError:
                # Preserve original behavior expected by tests: abort on HTTPError
                raise
            except requests.RequestException as req_e:
                logger.error(f"Network error fetching {target_label}: {req_e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error fetching {target_label}: {e}")
                continue

        logger.info(f"Prepared {len(files_to_validate)} files for validation")
        logger.debug(f"Example file objects (up to 2): {json.dumps(files_to_validate[:2])}")
        print(f"files_to_validate_count: {len(files_to_validate)}")
        return files_to_validate
        
    except requests.HTTPError as e:
        logger.error(f"HTTP error while fetching files: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching files from backend: {e}")
        return []
    finally:
        # If we were given a session, we assume the caller manages its lifecycle
        pass

def fetch_schema_for_type(backend_uri: str, obj_type: str, auth: Tuple[str, str]) -> Dict[str, Any]:
    """Fetch the schema properties for a given object type.
    
    Args:
        backend_uri: Base URI for the backend API
        obj_type: Type of object to fetch schema for
        auth: Tuple of (key_id, secret_key) for authentication
        
    Returns:
        Dictionary with schema properties
    """
    try:
        schema_url = urljoin(backend_uri, f'profiles/{obj_type}/?format=json')
        response = requests.get(schema_url, auth=auth)
        response.raise_for_status()
        return response.json().get('properties', {})
    except Exception as e:
        logger.error(f"Error fetching schema for {obj_type}: {e}")
        return {}

def convert_results_to_validation_records(results: List[Dict[str, Any]], 
                                         file_objects: List[Dict[str, Any]],
                                         portal_uri: str, 
                                         auth: Tuple[str, str]) -> List[FileValidationRecord]:
    """Convert validation results to FileValidationRecord objects.
    
    Args:
        results: List of validation result dictionaries
        file_objects: List of file metadata objects from the backend
        portal_uri: Base URI for the backend API
        auth: Tuple of (key_id, secret_key) for authentication
        
    Returns:
        List of FileValidationRecord objects
    """
    # Create mapping of identifier to file object for faster lookup
    file_map = {file_obj.get('accession', file_obj.get('uuid', '')): file_obj 
               for file_obj in file_objects}
    
    validation_records = []
    
    for result in results:
        if not result.get('success', False):
            continue
            
        identifier = result.get('identifier', '')
        if not identifier or identifier not in file_map:
            logger.warning(f"No file metadata found for result with identifier: {identifier}")
            continue
            
        # Get file metadata
        file_obj = file_map[identifier]
        uuid = file_obj.get('uuid', '')
        
        # Get ETag for the file
        etag = fetch_etag_for_uuid(portal_uri, uuid, auth)
        
        # Create validation record
        record = create_validation_record(result, result['file_path'], uuid, etag)
        validation_records.append(record)
        
    return validation_records

def main():
    """Main entry point for checkfiles utility."""
    global logger  # Move global declaration to the top of the function
    
    args = parse_arguments()
    
    # Log full command line arguments for debugging
    logger.debug(f"Command line arguments: {vars(args)}")
    print(f"Command line arguments: {vars(args)}")
    
    # Set up logging with custom path if provided
    if args.log_file:
        # Proper way to reconfigure logging
        logging.root.handlers = []  # Clear all handlers
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename=args.log_file,
            filemode='w'
        )
        # Don't need global logger declaration here since it's at the function start
        logger = logging.getLogger(__name__)
        logger.debug(f"Logging redirected to: {args.log_file}")
    
    # Initialize the validation_progress.log file with a header
    log_dir = os.getenv('CHECKFILES_LOG_DIR', os.getcwd())
    os.makedirs(log_dir, exist_ok=True)
    progress_log_path = os.path.join(log_dir, 'validation_progress.log')
    with open(progress_log_path, 'w') as f:
        f.write("identifier\turi\terrors\tresults\tjson_patch\tLattice patched?\tS3 tag patched?\n")
    
    # Check that only one file source is provided
    sources_provided = 0
    if args.local_file:
        sources_provided += 1
    if args.s3_file:
        sources_provided += 1
    if args.backend_uri and args.query:
        sources_provided += 1
    
    logger.debug(f"Sources provided: {sources_provided}")
    
    if sources_provided == 0:
        error_msg = "Error: You must specify one file source: local files (-l), S3 files (-s3), or a backend query (--backend-uri and --query)"
        logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
    
    if sources_provided > 1:
        error_msg = "Error: Only one file source can be used at a time. Choose one of: local files (-l), S3 files (-s3), or a backend query (--backend-uri and --query)"
        logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
    
    # Enforce file format rules:
    # 1. When using local or S3 files directly, -f is required
    # 2. When using backend API, -f must not be provided
    if (args.local_file or args.s3_file) and not args.file_format:
        error_msg = "Error: When using -l or -s3, you must specify a file format using the -f/--file-format option"
        logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
    
    if args.backend_uri and args.query and args.file_format:
        error_msg = "Error: When using --backend-uri and --query, the -f/--file-format option must not be provided"
        logger.warning(error_msg)
        logger.warning("The file format will be determined from the backend file information")
        print(error_msg)
        print("The file format will be determined from the backend file information")
        sys.exit(1)
    
    # Get list of files to process
    local_files = []
    s3_files = []
    backend_files = []
    s3_uri_to_file_format = {}  # Mapping of S3 URI to file format for backend files
    
    # If backend_uri and query are provided, fetch files from backend
    if args.backend_uri and args.query:
        logger.debug(f"Fetching files from backend: {args.backend_uri} with query: {args.query}")
        # Use a dedicated session with retries to avoid BrokenPipe and transient errors
        session = requests.Session()
        try:
            session.headers.update({'Connection': 'close'})
            retries = Retry(
                total=5,
                connect=5,
                read=5,
                status=5,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=frozenset(["GET"])  # only GETs here
            )
            adapter = HTTPAdapter(max_retries=retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            logger.debug("Initialized HTTP session with retries for backend fetch")

            backend_files = fetch_files_from_backend(args.backend_uri, args.query, session=session)
        finally:
            try:
                session.close()
            except Exception:
                pass
        logger.debug(f"Fetched {len(backend_files)} files from backend")
        
        # Build helper maps when in backend mode
        uuid_to_file = {}
        s3_uri_to_file = {}
        for file_obj in backend_files:
            if file_obj.get('s3_uri'):
                s3_uri = file_obj.get('s3_uri')
                s3_files.append(s3_uri)
                s3_uri_to_file[s3_uri] = file_obj
            if file_obj.get('uuid'):
                uuid_to_file[file_obj['uuid']] = file_obj
                
                # Extract file format from backend file object
                if file_obj.get('file_format'):
                    s3_uri_to_file_format[s3_uri] = file_obj.get('file_format')
                    logger.debug(f"Detected format for {s3_uri}: {file_obj.get('file_format')}")
                else:
                    logger.warning(f"File {s3_uri} has no file_format field in backend response")
                    print(f"Warning: File {s3_uri} has no file_format field in backend response")
    elif args.local_file:
        raw_local_files = [f.strip() for f in args.local_file.split(',')]
        logger.debug(f"Raw local files: {raw_local_files}")
        
        # Process each local file path through the path translator
        for file_path in raw_local_files:
            if is_s3_uri(file_path):
                logger.debug(f"Local file path is S3 URI: {file_path}")
                s3_files.append(file_path)
            else:
                resolved_path = resolve_path(file_path)
                logger.debug(f"Resolved path '{file_path}' to '{resolved_path}'")
                local_files.append(resolved_path)
    elif args.s3_file:
        s3_files = [f.strip() for f in args.s3_file.split(',')]
        logger.debug(f"S3 files to process: {s3_files}")
    
    total_files = len(local_files) + len(s3_files)
    logger.info(f"Total files to process: {total_files}")
    
    if total_files == 0:
        error_msg = "Error: No files found to validate"
        logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
    
    # Initialize activity tracker
    progress_tracker = None
    if not args.quiet:
        progress_tracker = SimpleActivityTracker(total_files)
    
    # Set a reasonable thread count based on file count and system resources
    thread_count = max(1, min(args.threads, total_files, multiprocessing.cpu_count()))
    logger.info(f"Using {thread_count} threads for parallel file processing")
    print(f"Using {thread_count} threads for parallel file processing")
    
    # Pre-validate gzip files before starting threads
    if local_files:
        validated_local_files = []
        for file_path in local_files:
            if has_gz_extension(file_path):
                logger.debug(f"Pre-validating gzip format for {file_path}")
                gzip_errors = validate_gzip_format(file_path)
                if gzip_errors:
                    logger.error(f"GZIP validation failed for {file_path}: {gzip_errors}")
                    print(f"GZIP validation failed for {file_path}: {gzip_errors}")
                    continue
            validated_local_files.append(file_path)
        local_files = validated_local_files
    
    # Process files in parallel with controlled concurrency
    # Build mapping structures for backend mode
    s3_uri_to_file_map = {}
    uuid_to_file_map = {}
    if backend_files:
        for f in backend_files:
            if f.get('s3_uri'):
                s3_uri_to_file_map[f['s3_uri']] = f
            if f.get('uuid'):
                uuid_to_file_map[f['uuid']] = f

    all_results = process_files_in_parallel(
        local_files=local_files,
        s3_files=s3_files,
        file_format=args.file_format,
        thread_count=thread_count,
        debug=args.debug,
        validator=None,  # No longer provide a pre-initialized validator
        progress_tracker=progress_tracker,
        backend_files=backend_files,
        s3_uri_to_file_format=s3_uri_to_file_format,  # Pass the mapping to the function
        update=args.update,
        backend_uri=args.backend_uri,
        s3_uri_to_file_map=s3_uri_to_file_map,
        uuid_to_file_map=uuid_to_file_map,
        ignore_active_credentials=args.ignore_active_credentials,
        update_s3_tags=args.update_s3_tags
    )
    
    # Close progress tracker
    if progress_tracker:
        progress_tracker.close()
    
    # Display summary
    display_summary(all_results)
    
    # Legacy batch patch step removed in favor of immediate per-file patching
    if args.update and not (args.backend_uri and args.query):
        logger.warning("The --update flag only works when using --backend-uri and --query")
        print("Warning: The --update flag only works when using --backend-uri and --query")

    # Upload validation log to S3 if running in AWS environment (when validation completes)
    s3_upload_result = upload_log_to_s3_if_aws_environment(args)
    if s3_upload_result:
        if s3_upload_result.get('status') == 'success':
            print(f"✅ Uploaded validation log to S3: {s3_upload_result['s3_key']}")
            logger.info(f"Validation log uploaded to S3: {s3_upload_result['s3_uri']}")
        else:
            print(f"❌ Failed to upload validation log to S3: {s3_upload_result.get('error', 'Unknown error')}")
            logger.error(f"S3 upload failed: {s3_upload_result.get('error', 'Unknown error')}")
    else:
        logger.debug("S3 upload not performed (not in AWS environment or not in backend mode)")

def process_files_in_parallel(local_files: List[str], s3_files: List[str], 
                              file_format: str, thread_count: int, debug: bool,
                              validator: Any, progress_tracker: SimpleActivityTracker = None,
                              backend_files: List[Dict[str, Any]] = None,
                              s3_uri_to_file_format: Dict[str, str] = {},
                              update: bool = False,
                              backend_uri: str = None,
                              s3_uri_to_file_map: Dict[str, Dict[str, Any]] = None,
                              uuid_to_file_map: Dict[str, Dict[str, Any]] = None,
                              ignore_active_credentials: bool = False,
                              update_s3_tags: bool = True) -> List[FileValidationRecord]:
    """Process multiple files in parallel using a process pool.
    
    Args:
        local_files: List of local file paths
        s3_files: List of S3 file paths
        file_format: Format of the files (used for local/S3 files without backend info)
        thread_count: Number of processes to use
        debug: Whether to enable debug output
        validator: Validator instance 
        progress_tracker: Activity tracker instance or None if tracking is disabled
        backend_files: List of file objects from the backend API
        s3_uri_to_file_format: Mapping of S3 URI to file format for backend files
        update: Whether to update the backend with results
        backend_uri: The URI of the backend API
        
    Returns:
        List of FileValidationRecord objects containing validation results
    """
    logger.info(f"Starting parallel processing with {thread_count} threads")
    print(f"Starting parallel processing with {thread_count} threads")
    
    # Create logs directory if it doesn't exist
    log_dir = os.getenv('CHECKFILES_LOG_DIR', os.path.join(os.getcwd(), 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    logger.debug(f"Ensuring log directory exists: {log_dir}")
    
    # Create scratch directory for temporary files if it doesn't exist
    scratch_dir = os.environ.get('SCRATCH_DIR', '/mnt/scratch')
    try:
        os.makedirs(scratch_dir, exist_ok=True)
        logger.debug(f"Ensuring scratch directory exists: {scratch_dir}")
    except (PermissionError, OSError) as e:
        scratch_dir = tempfile.gettempdir()
        logger.warning(f"Could not create/access scratch directory, using system temp: {scratch_dir}")
    
    # Fix file formats from backend if they are "hdf5"
    if backend_uri and s3_uri_to_file_format:
        logger.info("Checking file formats from backend for compatibility")
        for s3_uri, format_name in list(s3_uri_to_file_format.items()):
            logger.debug(f"Processing format for {s3_uri}:")
            logger.debug(f"  Original format from backend: {format_name}")
            
            if format_name and format_name.lower() == "hdf5":
                # Check S3 file extension to determine if it's h5 or h5ad
                file_name = os.path.basename(s3_uri).lower()
                logger.debug(f"  File extension check for {file_name}")
                
                if file_name.endswith('.h5ad'):
                    logger.info(f"Converting format 'hdf5' to 'h5ad' for {s3_uri}")
                    print(f"Converting format 'hdf5' to 'h5ad' for {s3_uri}")
                    s3_uri_to_file_format[s3_uri] = 'h5ad'
                elif file_name.endswith('.h5'):
                    logger.info(f"Converting format 'hdf5' to 'h5' for {s3_uri}")
                    print(f"Converting format 'hdf5' to 'h5' for {s3_uri}")
                    s3_uri_to_file_format[s3_uri] = 'h5'
                else:
                    error_msg = f"Error: File with format 'hdf5' has unrecognized extension: {file_name}"
                    logger.error(error_msg)
                    print(error_msg)
                    # Remove this file from processing
                    s3_uri_to_file_format.pop(s3_uri)
                    s3_files.remove(s3_uri)
            elif format_name and format_name.lower() not in ['fastq', 'h5', 'h5ad']:
                error_msg = f"Error: Unsupported file format from backend: {format_name}"
                logger.error(error_msg)
                print(error_msg)
                # Remove this file from processing
                s3_uri_to_file_format.pop(s3_uri)
                if s3_uri in s3_files:
                    s3_files.remove(s3_uri)
            
            logger.debug(f"  Final format after processing: {s3_uri_to_file_format.get(s3_uri, 'removed')}")
    
    # Debug the format mapping for S3 files
    if s3_uri_to_file_format:
        logger.debug(f"S3 file format mapping: {s3_uri_to_file_format}")
        print(f"S3 file format mapping: {s3_uri_to_file_format}")
    
    # Debug info to help identify serialization issues
    if progress_tracker:
        logger.debug(f"Progress tracker type: {type(progress_tracker)}")
        print(f"Progress tracker type: {type(progress_tracker)}")
    
    with ProcessPoolExecutor(max_workers=thread_count) as executor:
        futures = []
        
        # Process local files
        if local_files:
            logger.info(f"Processing {len(local_files)} local files...")
            print(f"Processing {len(local_files)} local files...")
            
            # Check if file format is supported
            try:
                # Test initializing a validator to catch errors early
                # Don't pass a specific file path here since we're just testing general format support
                logger.debug(f"Testing validator initialization for format: {file_format}")
                test_validator = initialize_validator(file_format, None)
                logger.debug(f"Test validator initialized: {type(test_validator).__name__}")
            except (ValueError, ImportError) as e:
                error_msg = f"Error initializing validator for format '{file_format}': {str(e)}"
                logger.error(error_msg)
                print(error_msg)
                sys.exit(1)
                
            for file_path in local_files:
                # DON'T pass the progress_tracker to the worker processes
                futures.append(
                    executor.submit(
                        validate_local_file,
                        file_path,
                        file_format,
                        debug,
                        validator,  # Pass the provided validator instance
                        None   # Don't pass progress_tracker to worker processes
                    )
                )
                
        # Process S3 files
        if s3_files:
            logger.info(f"Processing {len(s3_files)} S3 files...")
            print(f"Processing {len(s3_files)} S3 files...")

            # Create a mapping from S3 URI to accession
            s3_uri_to_accession = {}
            if backend_files:
                # Map S3 URIs to their accessions
                for file_obj in backend_files:
                    if file_obj.get('s3_uri') and file_obj.get('accession'):
                        s3_uri_to_accession[file_obj['s3_uri']] = file_obj['accession']
                logger.debug(f"Created mapping for {len(s3_uri_to_accession)} files with accessions")
                print(f"Created mapping for {len(s3_uri_to_accession)} files with accessions")
                
            # Submit validation tasks for each S3 file
            for s3_path in s3_files:
                # Determine file format for this file
                s3_file_format = s3_uri_to_file_format.get(s3_path)
                
                # If no format from backend, use the one provided on command line
                if not s3_file_format:
                    s3_file_format = file_format
                
                logger.debug(f"Using format '{s3_file_format}' for S3 file: {s3_path}")
                print(f"Using format '{s3_file_format}' for S3 file: {s3_path}")
                
                # For H5AD files, add additional logging
                if s3_file_format and s3_file_format.lower() in ['h5ad', 'h5']:
                    logger.info(f"H5AD/HDF5 file detected: {s3_path}")
                    logger.info("This format requires file download before validation")
                
                try:
                    # Test if the format is valid, but don't create the validator instance here
                    logger.debug(f"Testing validator for S3 file with format: {s3_file_format}")
                    try:
                        test_validator = initialize_validator(s3_file_format, s3_path)
                        logger.debug(f"Test validator initialized: {type(test_validator).__name__}")
                    except ValueError as ve:
                        # If the standard validator initialization fails, try to detect from filename
                        detected_format = detect_format_from_filename(s3_path)
                        if detected_format and detected_format != s3_file_format:
                            logger.info(f"Detected alternative format '{detected_format}' from filename, original was '{s3_file_format}'")
                            print(f"Detected alternative format '{detected_format}' from filename, will try this instead")
                            s3_file_format = detected_format
                            # Try again with the detected format
                            test_validator = initialize_validator(s3_file_format, s3_path)
                            logger.debug(f"Alternative validator initialized: {type(test_validator).__name__}")
                        else:
                            # Re-raise if we couldn't detect an alternative format
                            raise
                except (ValueError, ImportError) as e:
                    error_msg = f"Error initializing validator for S3 file {s3_path} with format '{s3_file_format}': {str(e)}"
                    logger.error(error_msg)
                    print(error_msg)
                    # Skip this file and continue with others
                    continue
                
                # Get identifier from mapping if available
                identifier = s3_uri_to_accession.get(s3_path, "")
                logger.debug(f"Using identifier '{identifier}' for S3 file: {s3_path}")
                
                # Every S3 validation goes through validate_s3_file, which knows how to handle 
                # special formats like h5ad that need downloading
                logger.info(f"Submitting S3 file for validation: {s3_path}")
                futures.append(
                    executor.submit(
                        validate_s3_file,
                        s3_path,
                        s3_file_format,  # Use the format for this specific file
                        debug,
                        validator,  # Pass the provided validator instance
                        None,  # Don't pass progress_tracker to worker processes
                        identifier,  # Pass the identifier if available
                        True,  # Return a FileValidationRecord
                        None  # No etag for concurrency control
                    )
                )
        
        # Prepare auth and schema cache for immediate patching
        portal_key = os.getenv('PORTAL_KEY')
        portal_secret_key = os.getenv('PORTAL_SECRET_KEY')
        auth = (portal_key, portal_secret_key) if portal_key and portal_secret_key else None
        schema_cache: Dict[str, Dict[str, Any]] = {}

        # Collect results as they complete
        all_results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
                
                # Update progress tracker in the main process if it exists
                if progress_tracker:
                    file_path = result.file_path if isinstance(result, FileValidationRecord) else result.get('file_path', 'unknown')
                    if isinstance(result, FileValidationRecord):
                        success = result.validation_success
                        # For the tracker, results should be a simple dict for errors if not successful
                        results_for_tracker = {'valid': result.info.get('valid', False), 'errors': result.errors, 'stats': result.info}
                    else:
                        success = result.get('success', False)
                        results_for_tracker = result.get('results', {})
                    
                    if success:
                        progress_tracker.complete_file(file_path, True, results_for_tracker)
                    else:
                        # Construct a detailed error message for logging and tracker
                        error_detail_for_log_and_tracker = "Unknown error"
                        actual_errors_dict = result.errors if isinstance(result, FileValidationRecord) else results_for_tracker.get('errors', {})
                        
                        if actual_errors_dict and isinstance(actual_errors_dict, dict):
                            error_messages = []
                            for err_key, err_val in actual_errors_dict.items():
                                if isinstance(err_val, dict) and 'message' in err_val:
                                    error_messages.append(f"{err_key}: {err_val['message']}")
                                elif isinstance(err_val, str):
                                    error_messages.append(f"{err_key}: {err_val}")
                                else:
                                    error_messages.append(f"{err_key}: {str(err_val)}") # Catch-all for other types
                            if error_messages:
                                error_detail_for_log_and_tracker = "; ".join(error_messages)
                        elif isinstance(actual_errors_dict, str): # If errors is just a string
                            error_detail_for_log_and_tracker = actual_errors_dict

                        logger.error(f"Validation indicated failure for {file_path}. Errors: {error_detail_for_log_and_tracker}")
                        progress_tracker.complete_file(file_path, False, {"error": error_detail_for_log_and_tracker})
                
                # Immediate per-file patching (backend mode + --update)
                try:
                    if update and backend_uri and isinstance(result, FileValidationRecord) and result.validation_success:
                        # Resolve file metadata using file_path (S3) or uuid
                        file_metadata = None
                        record_uuid = None
                        if is_s3_uri(result.file_path) and s3_uri_to_file_map:
                            file_metadata = s3_uri_to_file_map.get(result.file_path)
                            if file_metadata:
                                record_uuid = file_metadata.get('uuid')
                        if not file_metadata and result.uuid and uuid_to_file_map:
                            file_metadata = uuid_to_file_map.get(result.uuid)
                            record_uuid = result.uuid or (file_metadata.get('uuid') if file_metadata else None)

                        if file_metadata and auth and record_uuid:
                            # attach uuid and original etag to record if missing
                            if not result.uuid:
                                result.uuid = record_uuid
                            if not result.original_etag:
                                result.original_etag = fetch_etag_for_uuid(backend_uri, record_uuid, auth)

                            # credentials policy
                            credentials_ok = True
                            if not ignore_active_credentials:
                                credentials_ok = check_credentials_expired(backend_uri, record_uuid, auth)
                            if credentials_ok:
                                # schema type and cache
                                obj_types = file_metadata.get('@type', [])
                                schema_type = next((t for t in obj_types if t not in ['Item', 'File']), None)
                                if schema_type:
                                    if schema_type not in schema_cache:
                                        schema_cache[schema_type] = fetch_schema_for_type(backend_uri, schema_type, auth)
                                    schema_properties = schema_cache.get(schema_type, {})

                                    # compare to build post_json
                                    comparison = compare_with_db(result, file_metadata, schema_properties)
                                    post_json = comparison.get('post_json', {})
                                            if post_json:
                                                # make a slim record to patch only intended keys
                                                patch_record = FileValidationRecord(result.file_path, result.uuid, result.original_etag)
                                                # Avoid auto-adding validated by payload builder; compare_with_db already decided whether to include it
                                                patch_record.validation_success = None
                                                patch_record.update_info(post_json)

                                        # eTag re-check via If-Match in patch_file plus our pre-check
                                        current_etag = fetch_etag_for_uuid(backend_uri, record_uuid, auth)
                                        if result.original_etag and current_etag and current_etag != result.original_etag:
                                            logger.warning(f"ETag mismatch for {record_uuid}; skipping patch")
                                            result.update_errors({'patch_error': f'etag_mismatch original={result.original_etag} current={current_etag}'})
                                        else:
                                            # Record the exact payload used for patch in the result for logging
                                            try:
                                                result.patch_payload = post_json
                                            except Exception:
                                                pass
                                            patch_res = patch_file(backend_uri, auth, patch_record)
                                            # consider any non-error as success
                                            if isinstance(patch_res, dict) and patch_res.get('status') == 'error':
                                                # Store full structured error details for better diagnostics in logs
                                                result.update_errors({'patch_error': patch_res})
                                            else:
                                                result.patched = True
                                                # S3 tagging optional and only for lattice
                                                if update_s3_tags and ('lattice-data.org' in backend_uri) and file_metadata.get('s3_uri'):
                                                    tag_res = set_s3_tags(file_metadata['s3_uri'], True)
                                                    if tag_res.get('status') == 'success':
                                                        result.s3_tagged = True
                                                    else:
                                                        result.update_errors({'s3_tag_error': tag_res.get('status')})
                            else:
                                result.update_errors({'patch_skip': 'credentials_not_expired'})
                        else:
                            if not auth:
                                result.update_errors({'patch_skip': 'missing_auth_env'})
                            elif not file_metadata:
                                result.update_errors({'patch_skip': 'missing_file_metadata'})
                            elif not record_uuid:
                                result.update_errors({'patch_skip': 'missing_uuid'})
                except Exception as patch_ex:
                    logger.error(f"Per-file patch failed: {patch_ex}")
                    try:
                        result.update_errors({'patch_exception': str(patch_ex)})
                    except Exception:
                        pass

                # Write each result to validation_progress.log as it completes
                write_result_to_progress_log(result)
            except Exception as e:
                error_traceback = traceback.format_exc()
                logger.error(f"Error processing file: {str(e)}")
                logger.error(f"Traceback: {error_traceback}")
                print(f"Error processing file: {str(e)}")
                print(f"Traceback: {error_traceback}")
                error_result = FileValidationRecord("unknown")
                error_result.validation_success = False
                error_result.update_errors({'validation_error': str(e)})
                all_results.append(error_result)
                # Write error to validation_progress.log
                write_result_to_progress_log(error_result)
    
    return all_results

def display_summary(all_results: List[FileValidationRecord]) -> None:
    """Display a summary of validation results.
    
    Args:
        all_results: List of FileValidationRecord objects
    """
    total_files = len(all_results)
    count_content_valid = 0
    count_content_invalid = 0
    count_processing_failed = 0

    # Define keys that typically indicate a processing/infrastructure error
    # set by core.validation functions, rather than a file content validation error
    # from a specific format validator.
    processing_failure_error_keys = {
        'validation_error',  # Generic error from core.validation
        'download_error',
        'stream_error',
        'file_not_found', # As set by core.validation or validators before content check
        'validator_initialization_failed', # If core.validation indicates this
        # Errors from H5AD/H5Py that occur before/during scanpy content validation
        'is_hdf5', # e.g., "File is not a valid HDF5 format."
        'h5py_open_error',
        'is_h5py_check_error',
        'scanpy_read_error', # If scanpy itself fails to read/parse the file structure
        'file_existence' # From H5adValidator if file not found
    }

    for r in all_results:
        if r.validation_success:
            # validation_success being True means the validator ran
            # and deemed the content valid.
            count_content_valid += 1
        else:
            # validation_success is False. This could be due to:
            # 1. A processing failure (e.g., download, file open, validator init).
            # 2. A content validation failure (validator ran, found content errors).
            is_processing_failure = False
            if r.errors:
                # Check if any of the reported error keys indicate a processing failure.
                if any(err_key in processing_failure_error_keys for err_key in r.errors.keys()):
                    is_processing_failure = True
                # Handle cases where r.errors might be a string (though less likely for FileValidationRecord)
                elif isinstance(r.errors, str) and any(pf_key in r.errors for pf_key in processing_failure_error_keys):
                    is_processing_failure = True
            
            if is_processing_failure:
                count_processing_failed += 1
            else:
                # If not a clear processing failure, and validation_success is False,
                # it's considered a content invalidity.
                count_content_invalid += 1
    
    print("\n=== Validation Summary ===")
    print(f"Total files submitted: {total_files}")
    print(f"Files with valid content: {count_content_valid}")
    print(f"Files with invalid content: {count_content_invalid}")
    print(f"Files that failed processing (e.g., download/read errors): {count_processing_failed}")
    
    # Print detailed results
    print("\n=== Detailed Results ===")
    for result in all_results:
        success = result.validation_success
        file_path = result.file_path
        info = result.info
        errors = result.errors
        valid = info.get('valid', False) if success else False

        if success:
            validity = "Valid" # If success is true, content is valid
            print(f"{file_path}: {validity}")
            
            # Print hash values if they exist
            if info:
                # Print file sizes
                if "file_size" in info:
                    print(f"  File size: {info['file_size']} bytes")
                if "content_size" in info:
                    print(f"  Uncompressed size: {info['content_size']} bytes")
                
                # Print hash values
                if "md5sum" in info:
                    print(f"  MD5: {info['md5sum']}")
                if "sha256" in info:
                    print(f"  SHA256: {info['sha256']}")
                if "crc32c" in info:
                    print(f"  CRC32C: {info['crc32c']}")
                if "content_md5sum" in info:
                    print(f"  Content MD5: {info['content_md5sum']}")
            
            if not valid and errors: # This 'valid' is info.get('valid'), 'success' is record.validation_success
                                     # If success is True, valid will also be True. This block seems unreachable if success is True.
                                     # Let's simplify: if success (content is valid), no content errors to print here.
                pass # Errors for valid files are not expected here.
            if isinstance(result, dict) and result.get('results', {}).get('warnings'): # old structure, less relevant now
                warnings_dict = result.get('results', {}).get('warnings')
                if warnings_dict:
                    print(f"  Warnings: {warnings_dict}")
            elif isinstance(result, FileValidationRecord) and result.info.get('warnings'): # new structure
                 warnings_dict = result.info.get('warnings')
                 if warnings_dict:
                    print(f"  Warnings:")
                    for warn_key, warn_value in warnings_dict.items():
                        if isinstance(warn_value, dict) and 'message' in warn_value:
                             print(f"    - {warn_value['message']}")
                        else:
                             print(f"    - {str(warn_value)}")

        else: # success (FileValidationRecord.validation_success) is False
            # Determine if it was a processing failure or content invalidity for the message
            is_processing_failure_detail = False
            if r.errors and any(err_key in processing_failure_error_keys for err_key in r.errors.keys()):
                is_processing_failure_detail = True

            if is_processing_failure_detail:
                print(f"{file_path}: Failed during processing")
            else:
                print(f"{file_path}: Invalid content")

            if errors:
                print("  Errors:")
                for error_key, error_value in errors.items():
                    if isinstance(error_value, dict):
                        print(f"    - {error_value.get('message', error_key)}")
                    else:
                        print(f"    - {error_value}")

def detect_format_from_filename(file_path: str) -> str:
    """Detect the likely format of a file based on its file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        String representing the detected format, or empty string if unknown
    """
    file_name = os.path.basename(file_path).lower()
    
    # Remove compression extensions first
    if file_name.endswith('.gz'):
        file_name = file_name[:-3]
    elif file_name.endswith('.bz2'):
        file_name = file_name[:-4]
    elif file_name.endswith('.zip'):
        file_name = file_name[:-4]
    
    # Check for supported extensions ONLY (fastq, h5, h5ad)
    if file_name.endswith('.fastq') or file_name.endswith('.fq'):
        return 'fastq'
    elif file_name.endswith('.h5ad'):
        return 'h5ad'
    elif file_name.endswith('.h5'):
        return 'h5'
    
    # Unknown/unsupported format
    return ''

def validate_s3_file(s3_path: str, file_format: str, debug: bool = False,
                   validator: Optional[Any] = None, 
                   progress_tracker: Optional[SimpleActivityTracker] = None,
                   identifier: str = "", return_record: bool = False,
                   etag: Optional[str] = None) -> FileValidationRecord:
    """Validate an S3 file using the core validation functionality.
    
    This is a wrapper around the core validate_s3_file function that maintains
    backward compatibility with the existing interface.
    
    Args:
        s3_path: S3 URI of the file to validate
        file_format: Format of the file
        debug: Whether to enable debug output
        validator: Validator instance or None to create one
        progress_tracker: Activity tracker instance or None if tracking is disabled
        identifier: Identifier for the file (e.g., accession)
        return_record: Whether to return a FileValidationRecord (always True now)
        etag: Optional ETag value for concurrency control
        
    Returns:
        FileValidationRecord containing validation results
    """
    print(f"Starting validation of S3 file: {s3_path} with format: {file_format}")
    logger.info(f"Starting validation of S3 file: {s3_path} with format: {file_format}")
    
    try:
        # Call the core validation function
        result = core_validate_s3_file(
            s3_path=s3_path,
            file_format=file_format,
            debug=debug,
            validator=validator,
            progress_tracker=progress_tracker,
            identifier=identifier,
            return_record=True,  # Always return record
            etag=etag
        )
        
        # Handle non-FileValidationRecord results
        if not isinstance(result, FileValidationRecord):
            error_msg = f"Unexpected result type: {type(result)}"
            logger.error(error_msg)
            return create_validation_record({
                "file_path": s3_path,
                "error": error_msg,
                "success": False,
                "identifier": identifier
            }, s3_path, identifier, etag)
            
        return result
        
    except Exception as e:
        error_msg = f"Error validating {s3_path}: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return create_validation_record({
            "file_path": s3_path,
            "error": error_msg,
            "success": False,
            "identifier": identifier
        }, s3_path, identifier, etag)

# Add a new function to robustly initialize validators with better error handling
def robust_initialize_validator(file_format, file_path):
    """Initialize a validator with robust error handling.
    
    This is a wrapper around initialize_validator that includes better error
    handling and fallback mechanisms.
    
    Args:
        file_format: Format of the file to validate
        file_path: Path to the file to validate
        
    Returns:
        Validator instance
    
    Raises:
        ValueError: If the validator could not be initialized
    """
    logger.debug(f"Robust validator initialization for format '{file_format}' and file: {file_path}")
    
    # Validate inputs
    if not file_format:
        if file_path:
            # Try to detect format from filename
            detected_format = detect_format_from_filename(file_path)
            if detected_format:
                logger.info(f"Detected format '{detected_format}' from filename")
                file_format = detected_format
            else:
                raise ValueError("No file format specified and could not detect from filename")
        else:
            raise ValueError("No file format specified and no file path to detect from")
    
    # Try to import the validator module directly
    validator_class = None
    
    # Map of format names to validator module paths
    validator_map = {
        'fastq': 'src.validators.fastq_validator.FastqValidator',
        'h5ad': 'src.validators.h5ad_validator.H5adValidator',
        'h5': 'src.validators.h5_validator.H5Validator',
    }
    
    # Check if we support this file format
    if file_format.lower() not in validator_map:
        raise ValueError(f"Unsupported file format: {file_format}")
    
    module_path = validator_map.get(file_format.lower())
    
    # Try to import the validator directly
    try:
        module_parts = module_path.split('.')
        class_name = module_parts[-1]
        module_path = '.'.join(module_parts[:-1])
        
        logger.debug(f"Importing {module_path} for class {class_name}")
        module = __import__(module_path, fromlist=[class_name])
        validator_class = getattr(module, class_name)
        logger.debug(f"Successfully imported validator class: {validator_class.__name__}")
    except (ImportError, AttributeError) as e:
        logger.error(f"Could not import validator for {file_format}: {e}")
        # Fall back to the original initialize_validator function
        logger.debug("Falling back to original initialize_validator")
        return initialize_validator(file_format, file_path)
    
    # Create and return the validator instance
    try:
        validator = validator_class(file_path)
        logger.debug(f"Created validator instance: {type(validator).__name__}")
        return validator
    except Exception as e:
        logger.error(f"Error creating validator instance: {e}")
        raise ValueError(f"Could not create validator for {file_format}: {e}")

def upload_log_to_s3_if_aws_environment(args=None):
    """Upload validation log to S3 if running in AWS environment.
    
    This function detects if we're running in AWS environment and uploads
    the validation progress log to S3 for later processing.
    
    Args:
        args: Command line arguments from parse_arguments()
    
    Returns:
        dict: Upload result with status and S3 key, or None if not in AWS environment
    """
    # Check if we should upload (only in backend mode)
    if not (args and args.backend_uri and args.query):
        logger.debug("Not in backend mode, skipping S3 upload")
        return None
    
    # Check if we're in AWS environment
    if not os.getenv('CHECKFILES_LOG_DIR'):
        logger.debug("CHECKFILES_LOG_DIR not set, not in AWS environment")
        return None
        
    if not AWS_AVAILABLE:
        logger.warning("boto3 not available, cannot upload to S3")
        return None
    
    try:
        # Get environment variables
        log_dir = os.getenv('CHECKFILES_LOG_DIR', os.getcwd())
        instance_suffix = os.getenv('INSTANCE_NAME_SUFFIX', 'unknown')
        
        # Check if validation log exists
        log_file_path = os.path.join(log_dir, 'validation_progress.log')
        if not os.path.exists(log_file_path):
            logger.warning(f"Validation log file not found: {log_file_path}")
            return None
        
        # Give file system time to flush all worker writes to disk
        logger.info("Waiting for file system to flush all writes...")
        time.sleep(2)
        
        # Force file system sync to ensure all pending writes are committed
        try:
            import subprocess
            subprocess.run(['sync'], check=False, capture_output=True)
            logger.debug("File system sync completed")
        except Exception as sync_e:
            logger.debug(f"Could not run sync command: {sync_e}")
            
        # Read log content
        with open(log_file_path, 'r') as f:
            log_content = f.read()
            
        if not log_content.strip():
            logger.warning("Validation log file is empty")
            return None
            
        logger.info(f"Uploading validation log to S3 (size: {len(log_content)} bytes)")
        
        # Create S3 key with timestamp
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        s3_key = f"reports/checkfiles-report-{instance_suffix}-{timestamp}.tsv"
        s3_bucket_name = 'lattice-checkfiles'
        
        # Upload to S3
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=s3_bucket_name,
            Key=s3_key,
            Body=log_content.encode('utf-8'),
            ContentType='text/tab-separated-values',
            Metadata={
                'checkfiles-instance': instance_suffix,
                'upload-timestamp': timestamp,
                'uploaded-by': 'checkfiles-script'
            }
        )
        
        logger.info(f"Successfully uploaded validation log to S3: s3://{s3_bucket_name}/{s3_key}")
        
        # Write S3 location info for upload_report lambda
        s3_info = {
            's3_key': s3_key,
            's3_bucket': s3_bucket_name,
            's3_uri': f"s3://{s3_bucket_name}/{s3_key}",
            'timestamp': timestamp,
            'instance_suffix': instance_suffix
        }
        
        s3_info_path = os.path.join(log_dir, 's3_upload_info.json')
        with open(s3_info_path, 'w') as f:
            json.dump(s3_info, f, indent=2)
            
        logger.info(f"S3 upload info written to: {s3_info_path}")
        
        return {
            'status': 'success',
            's3_key': s3_key,
            's3_bucket': s3_bucket_name,
            's3_uri': f"s3://{s3_bucket_name}/{s3_key}",
            'timestamp': timestamp
        }
        
    except Exception as e:
        error_msg = f"Error uploading validation log to S3: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'status': 'failed',
            'error': error_msg
        }

if __name__ == "__main__":
    main()
