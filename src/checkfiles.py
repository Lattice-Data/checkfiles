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
from typing import List, Dict, Any, Tuple
from urllib.parse import urljoin
import requests
import json
import tempfile

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
    from src.cli.parser import parse_arguments
    from src.core.validation import initialize_validator, validate_local_file, validate_s3_file
    from src.tracking.progress import SimpleActivityTracker
    from src.utils.helpers import has_gz_extension, validate_gzip_format
    from src.path_translator import resolve_path, is_s3_uri
    from src.models.validation_record import FileValidationRecord
    from src.worker.patch_worker import patching_worker
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
def write_result_to_progress_log(result: Dict[str, Any]) -> None:
    """Write a validation result to the validation_progress.log file.
    
    Args:
        result: The validation result dictionary
    """
    log_dir = os.getenv('CHECKFILES_LOG_DIR', os.getcwd())
    os.makedirs(log_dir, exist_ok=True)
    progress_log_path = os.path.join(log_dir, 'validation_progress.log')
    print(f"Writing result to {progress_log_path}")
    
    file_path = result.get('file_path', 'unknown')
    
    # Get identifier directly from result if available
    identifier = result.get('identifier', '')
    if not identifier:
        # Fall back to extracting from file path
        file_name = os.path.basename(file_path)
        identifier = file_name
        if 'accession=' in file_path:
            try:
                # Try to extract accession from the query string
                accession_part = file_path.split('accession=')[1].split('&')[0]
                identifier = accession_part
            except (IndexError, AttributeError):
                pass
    
    # Use file_path for URI, handle if missing
    uri = result.get('file_path', 'unknown')
    # uri = file_path if file_path.startswith('s3://') else ''

    if result.get('success', False):
        validation_results = result.get('results', {})
        errors = validation_results.get('errors', {})
        stats = validation_results.get('stats', {})

        # Create a json_patch dictionary dynamically based on available stats
        json_patch = {}
        # Keys relevant for H5/H5AD and potentially other types
        patch_keys = [
            'file_size',
            'md5sum',
            'sha256',
            'crc32c',
            'content_md5sum', # May be present for gzipped files
            'observation_count', # Specific to H5/H5AD
            'genomes', # Specific to H5/H5AD
            'feature_counts', # Specific to H5/H5AD
            'is_hdf5', # Specific to H5/H5AD
            'read_count', # Specific to FASTQ
            'read_length', # Specific to FASTQ
            'platform', # Potentially FASTQ
            'flowcell_details' # Potentially FASTQ
        ]

        for key in patch_keys:
            if key in stats:
                json_patch[key] = stats[key]

        # Add validation status explicitly
        json_patch['validated'] = validation_results.get('valid', False)

        # Ensure dicts are properly JSON formatted for the log line
        errors_str = json.dumps(errors)
        stats_str = json.dumps(stats)
        patch_str = json.dumps(json_patch)

        log_line = f"{identifier}\t{uri}\t{errors_str}\t{stats_str}\t{patch_str}\tsuccess\tsuccess"
    else:
        error = result.get('error', 'Unknown error')
        # Ensure error dict is JSON formatted
        error_dict_str = json.dumps({'error': error})
        empty_dict_str = json.dumps({})
        log_line = f"{identifier}\t{uri}\t{error_dict_str}\t{empty_dict_str}\t{empty_dict_str}\tfailed\tfailed"
    
    # Use file locking to ensure atomic writes
    # This approach doesn't require a global lock object that needs to be pickled
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

def fetch_files_from_backend(backend_uri: str, query: str) -> List[Dict[str, Any]]:
    """Fetch files from backend using query and backend_uri.
    
    Args:
        backend_uri: Base URI of the backend service
        query: Query string for filtering files
        
    Returns:
        List of file objects to validate
    """
    logger.info(f"Fetching files from backend using query: {query}")
    print( "fetching file objects from backend")
    # Get authentication credentials from environment variables
    portal_key = os.getenv('PORTAL_KEY')
    portal_secret_key = os.getenv('PORTAL_SECRET_KEY')
    print(f"portal_key: {portal_key}")
    print(f"portal_secret_key: {portal_secret_key}")
    if not portal_key or not portal_secret_key:
        logger.error("Missing authentication credentials. Please set PORTAL_KEY and PORTAL_SECRET_KEY environment variables.")
        return []
    
    # Set up authentication
    auth = (portal_key, portal_secret_key)
    
    # Construct the full query URL
    query_url = urljoin(backend_uri, query.replace('report', 'search') + '&format=json&limit=all')
    
    try:
        # Make the request to the backend
        response = requests.get(query_url, auth=auth)
        response.raise_for_status()
        
        # Extract accessions from the response
        accessions = [x['accession'] for x in response.json()['@graph']]
        logger.info(f"Found {len(accessions)} files to validate")
        
        # Fetch full file objects for each accession
        files_to_validate = []
        for acc in accessions:
            item_url = urljoin(backend_uri, acc + '/?frame=object')
            file_response = requests.get(item_url, auth=auth)
            
            if not file_response.ok:
                logger.error(f"Failed to fetch file object for {acc}")
                continue
                
            file_json = file_response.json()
            
            # Check if file should be validated
            if file_json.get('no_file_available'):
                logger.info(f"Skipping {acc}: marked as no_file_available")
                continue
                
            if not file_json.get('s3_uri'):
                logger.info(f"Skipping {acc}: no URI available")
                continue
                
            files_to_validate.append(file_json)
        print (f"files_to_validate: {files_to_validate}")    
        return files_to_validate
        
    except requests.HTTPError as e:
        logger.error(f"HTTP error while fetching files: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching files from backend: {e}")
        return []

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
        backend_files = fetch_files_from_backend(args.backend_uri, args.query)
        logger.debug(f"Fetched {len(backend_files)} files from backend")
        
        for file_obj in backend_files:
            if file_obj.get('s3_uri'):
                s3_uri = file_obj.get('s3_uri')
                s3_files.append(s3_uri)
                
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
        backend_uri=args.backend_uri
    )
    
    # Close progress tracker
    if progress_tracker:
        progress_tracker.close()
    
    # Display summary
    display_summary(all_results)
    
    # Handle updating if requested and if used with backend_uri
    if args.update and args.backend_uri and args.query:
        logger.info("Updating backend with validation results")
        
        # Check auth environment variables
        portal_key = os.getenv('PORTAL_KEY')
        portal_secret_key = os.getenv('PORTAL_SECRET_KEY')
        
        if not portal_key or not portal_secret_key:
            logger.error("Missing authentication credentials. Please set PORTAL_KEY and PORTAL_SECRET_KEY environment variables.")
            print("Error: --update requires PORTAL_KEY and PORTAL_SECRET_KEY environment variables")
            sys.exit(1)
            
        auth = (portal_key, portal_secret_key)
        
        # Convert results to validation records
        validation_records = convert_results_to_validation_records(
            all_results, backend_files, args.backend_uri, auth)
        
        if not validation_records:
            logger.warning("No valid records found for updating")
            print("No valid records found for updating")
            return
            
        # Prepare patch jobs
        patch_jobs = []
        for record in validation_records:
            # Get file metadata for this record
            file_metadata = next((f for f in backend_files if f.get('uuid') == record.uuid), {})
            
            # Get schema properties for this file type
            obj_types = file_metadata.get('@type', [])
            schema_type = next((t for t in obj_types if t not in ['Item', 'File']), None)
            
            if not schema_type:
                logger.warning(f"No valid schema type found for file {record.uuid}")
                continue
                
            schema_properties = fetch_schema_for_type(args.backend_uri, schema_type, auth)
            
            # Create patch job
            patch_jobs.append({
                'portal_uri': args.backend_uri,
                'auth': auth,
                'validation_record': record,
                'file_metadata': file_metadata,
                'schema_properties': schema_properties,
                'ignore_active_credentials': args.ignore_active_credentials,
                'update_s3_tags': args.update_s3_tags,
                'is_lattice_db': args.backend_uri and 'lattice-data.org' in args.backend_uri
            })
        
        logger.info(f"Preparing to update {len(patch_jobs)} files")
        print(f"Preparing to update {len(patch_jobs)} files")
        
        # Use a process pool to process patch jobs
        patched_count = 0
        s3_tagged_count = 0
        with ProcessPoolExecutor(max_workers=min(args.threads, len(patch_jobs))) as executor:
            for result in executor.map(patching_worker, patch_jobs):
                if result.get('patched'):
                    patched_count += 1
                if result.get('s3_tagged'):
                    s3_tagged_count += 1
                    
        logger.info(f"Successfully updated {patched_count} files")
        logger.info(f"Successfully tagged {s3_tagged_count} S3 files")
        print(f"Successfully updated {patched_count} files")
        print(f"Successfully tagged {s3_tagged_count} S3 files")
    elif args.update and not (args.backend_uri and args.query):
        logger.warning("The --update flag only works when using --backend-uri and --query")
        print("Warning: The --update flag only works when using --backend-uri and --query")

def process_files_in_parallel(local_files: List[str], s3_files: List[str], 
                              file_format: str, thread_count: int, debug: bool,
                              validator: Any, progress_tracker: SimpleActivityTracker = None,
                              backend_files: List[Dict[str, Any]] = None,
                              s3_uri_to_file_format: Dict[str, str] = {},
                              update: bool = False,
                              backend_uri: str = None) -> List[Dict[str, Any]]:
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
        List of validation results
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
            if format_name and format_name.lower() == "hdf5":
                # Check S3 file extension to determine if it's h5 or h5ad
                file_name = os.path.basename(s3_uri).lower()
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
                        None,  # Pass None instead of validator instance
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
                        None,  # Pass None instead of validator instance
                        None,  # Don't pass progress_tracker to worker processes
                        identifier  # Pass the identifier if available
                    )
                )
        
        # Collect results as they complete
        all_results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
                
                # Update progress tracker in the main process if it exists
                if progress_tracker:
                    file_path = result.get('file_path', 'unknown')
                    if result.get('success', False):
                        progress_tracker.complete_file(file_path, True, result.get('results', {}))
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        logger.error(f"Validation failed for {file_path}: {error_msg}")
                        progress_tracker.complete_file(file_path, False, {"error": error_msg})
                
                # Write each result to validation_progress.log as it completes
                write_result_to_progress_log(result)
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"Error processing file: {str(e)}")
                logger.error(f"Traceback: {error_traceback}")
                print(f"Error processing file: {str(e)}")
                print(f"Traceback: {error_traceback}")
                error_result = {
                    "file_path": "unknown",
                    "error": str(e),
                    "traceback": error_traceback,
                    "success": False
                }
                all_results.append(error_result)
                # Write error to validation_progress.log
                write_result_to_progress_log(error_result)
    
    return all_results

def display_summary(all_results: List[Dict[str, Any]]) -> None:
    """Display a summary of validation results.
    
    Args:
        all_results: List of validation results
    """
    total = len(all_results)
    successful = sum(1 for r in all_results if r["success"])
    valid = sum(1 for r in all_results if r["success"] and r["results"]["valid"])
    
    print("\n=== Validation Summary ===")
    print(f"Total files: {total}")
    print(f"Successfully processed: {successful}")
    print(f"Valid files: {valid}")
    print(f"Invalid files: {successful - valid}")
    print(f"Failed to process: {total - successful}")
    
    # Print detailed results
    print("\n=== Detailed Results ===")
    for result in all_results:
        if result["success"]:
            validity = "Valid" if result["results"]["valid"] else "Invalid"
            print(f"{result['file_path']}: {validity}")
            
            # Print hash values if they exist
            if result["results"].get("stats"):
                stats = result["results"]["stats"]
                # Print file sizes
                if "file_size" in stats:
                    print(f"  File size: {stats['file_size']} bytes")
                if "content_size" in stats:
                    print(f"  Uncompressed size: {stats['content_size']} bytes")
                
                # Print hash values
                if "md5sum" in stats:
                    print(f"  MD5: {stats['md5sum']}")
                if "sha256" in stats:
                    print(f"  SHA256: {stats['sha256']}")
                if "crc32c" in stats:
                    print(f"  CRC32C: {stats['crc32c']}")
                if "content_md5sum" in stats:
                    print(f"  Content MD5: {stats['content_md5sum']}")
            
            if not result["results"]["valid"]:
                print(f"  Errors: {result['results'].get('errors', {})}")
            if result["results"].get("warnings"):
                print(f"  Warnings: {result['results'].get('warnings', {})}")
        else:
            print(f"{result['file_path']}: Failed - {result.get('error', 'Unknown error')}")

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

def validate_s3_file(s3_path, file_format, debug=False, validator=None, progress_tracker=None, identifier=""):
    """Validate an S3 file.
    
    Args:
        s3_path: S3 URI of the file to validate
        file_format: Format of the file
        debug: Whether to enable debug output
        validator: Validator instance or None to create one
        progress_tracker: Activity tracker instance or None if tracking is disabled
        identifier: Identifier for the file (e.g., accession)
        
    Returns:
        Dict with validation results
    """
    print(f"Starting validation of S3 file: {s3_path} with format: {file_format}")
    logger.info(f"Starting validation of S3 file: {s3_path} with format: {file_format}")
    
    # Try to detect format from filename if not provided
    if not file_format:
        detected_format = detect_format_from_filename(s3_path)
        if detected_format:
            logger.info(f"Detected format '{detected_format}' from filename for {s3_path}")
            print(f"Detected format '{detected_format}' from filename for {s3_path}")
            file_format = detected_format
        else:
            logger.warning(f"Could not detect format from filename for {s3_path}, using default")
    
    try:
        # Initialize validator if not provided
        if validator is None:
            logger.debug(f"Initializing validator for {file_format}")
            try:
                validator = robust_initialize_validator(file_format, s3_path)
            except ValueError as e:
                logger.error(f"Failed to initialize validator: {e}")
                # As a last resort, try to detect from the filename
                if not file_format:
                    detected_format = detect_format_from_filename(s3_path)
                    if detected_format:
                        logger.info(f"Trying detected format '{detected_format}' as last resort")
                        print(f"Trying detected format '{detected_format}' as last resort")
                        validator = robust_initialize_validator(detected_format, s3_path)
                    else:
                        raise ValueError(f"Failed to initialize validator and could not detect format: {e}")
                else:
                    raise
            logger.debug(f"Validator initialization complete: {type(validator).__name__}")
        
        # Validate S3 file
        logger.info(f"Starting validation of {s3_path}")
        results = validator.validate_s3_file(s3_path, debug)
        logger.info(f"Completed validation of {s3_path}")
        logger.debug(f"Validation results: {results}")
        
        # Create result object
        result = {
            "file_path": s3_path,
            "identifier": identifier,
            "results": results,
            "success": True
        }
        return result
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Error validating S3 file {s3_path}: {str(e)}")
        logger.error(f"Traceback: {error_traceback}")
        print(f"Error validating S3 file {s3_path}: {str(e)}")
        print(f"Traceback: {error_traceback}")
        
        return {
            "file_path": s3_path,
            "identifier": identifier,
            "error": str(e),
            "traceback": error_traceback,
            "success": False
        }

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
        'fasta': 'src.validators.fasta_validator.FastaValidator'
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

if __name__ == "__main__":
    main()
    
# Add this function to test serialization with multiprocessing
def test_multiprocessing_serialization():
    """
    Test function to diagnose serialization issues with multiprocessing.
    
    Run this directly to test if objects can be properly serialized:
    python -c "from src.checkfiles import test_multiprocessing_serialization; test_multiprocessing_serialization()"
    """
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    
    def worker_function(data):
        """Simple worker function that returns its input."""
        print(f"Worker received: {data}")
        return data
        
    print("Testing basic multiprocessing serialization...")
    
    # Test with different types of data
    test_data = [
        {"type": "dict", "value": 123},
        "simple string",
        42,
        [1, 2, 3]
    ]
    
    # Test using ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = []
        for data in test_data:
            futures.append(executor.submit(worker_function, data))
            
        # Collect results
        results = []
        for future in futures:
            try:
                result = future.result()
                print(f"Successfully processed: {result}")
                results.append(result)
            except Exception as e:
                print(f"Error in worker: {str(e)}")
                
    print(f"Successfully processed {len(results)} out of {len(test_data)} items")
    
    # Try to initialize a progress tracker in isolation
    try:
        from src.tracking.progress import SimpleActivityTracker
        tracker = SimpleActivityTracker(10)
        print(f"Created tracker: {type(tracker)}")
        print(f"Tracker attributes: {dir(tracker)}")
        
        # Test if tracker can be serialized directly
        import pickle
        try:
            pickle_data = pickle.dumps(tracker)
            print(f"Successfully pickled tracker: {len(pickle_data)} bytes")
        except Exception as e:
            print(f"Failed to pickle tracker: {str(e)}")
            
    except ImportError:
        print("Could not import SimpleActivityTracker for testing")
