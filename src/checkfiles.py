#!/usr/bin/env python3
"""
Checkfiles utility - validates file formats like FASTQ.
Handles files from local paths, S3, or stdin.
"""

import sys
import os
import concurrent.futures
import multiprocessing
import logging
import threading
from typing import List, Dict, Any
from urllib.parse import urljoin
import requests

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
from src.cli.parser import parse_arguments
from src.core.validation import initialize_validator, validate_local_file, validate_s3_file
from src.tracking.progress import SimpleActivityTracker
from src.utils.helpers import has_gz_extension, validate_gzip_format
from src.path_translator import resolve_path, is_s3_uri

# Create a lock for thread-safe writing to validation_progress.log
validation_log_lock = threading.Lock()

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
    if result.get('success', False):
        validity = "Valid" if result.get('results', {}).get('valid', False) else "Invalid"
        errors = result.get('results', {}).get('errors', {})
        warnings = result.get('results', {}).get('warnings', {})
        stats = result.get('results', {}).get('stats', {})
        
        # Include all stats, not just a subset
        details = [f"{k}={v}" for k, v in stats.items()] if stats else []
        details_str = "\t".join(details)
        error_str = "\t".join([f"{k}={v}" for k, v in errors.items()]) if errors else ""
        warning_str = "\t".join([f"{k}={v}" for k, v in warnings.items()]) if warnings else ""
        
        log_line = f"{file_path}\t{validity}\t{details_str}"
        if error_str:
            log_line += f"\tErrors: {error_str}"
        if warning_str:
            log_line += f"\tWarnings: {warning_str}"
    else:
        error = result.get('error', 'Unknown error')
        log_line = f"{file_path}\tFailed\tError: {error}"
    
    with validation_log_lock:
        with open(progress_log_path, 'a') as f:
            f.write(f"{log_line}\n")
            f.flush()
            os.fsync(f.fileno())  # Ensure data is written to disk

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
    query_url = urljoin(backend_uri, query.replace('report', 'search') + '&format=json&limit=all&field=accession')
    
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



def main():
    """Main entry point for checkfiles utility."""
    args = parse_arguments()
    
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
        global logger
        logger = logging.getLogger(__name__)
        logger.debug(f"Logging redirected to: {args.log_file}")
    
    # Initialize the validation_progress.log file with a header
    log_dir = os.getenv('CHECKFILES_LOG_DIR', os.getcwd())
    os.makedirs(log_dir, exist_ok=True)
    progress_log_path = os.path.join(log_dir, 'validation_progress.log')
    with open(progress_log_path, 'w') as f:
        f.write("# Validation Progress Log\n")
        f.write("# File\tStatus\tDetails\n")
    
    # Check if file format is supported
    if not args.file_format:
        print("Please specify a file format using the -f/--file-format option")
        return
        
    # Initialize validator
    try:
        validator = initialize_validator(args.file_format)
    except ValueError as e:
        print(str(e))
        return
    except ImportError as e:
        print(str(e))
        return
        
    # Get list of files to process
    local_files = []
    s3_files = []
    backend_files = []
    
    # If backend_uri and query are provided, fetch files from backend
    if args.backend_uri and args.query:
        backend_files = fetch_files_from_backend(args.backend_uri, args.query)
        for file_obj in backend_files:
            if file_obj.get('s3_uri'):
                s3_files.append(file_obj['s3_uri'])

    
    if args.local_file:
        raw_local_files = [f.strip() for f in args.local_file.split(',')]
        
        # Process each local file path through the path translator
        for file_path in raw_local_files:
            if is_s3_uri(file_path):
                s3_files.append(file_path)
            else:
                resolved_path = resolve_path(file_path)
                logger.debug(f"Resolved path '{file_path}' to '{resolved_path}'")
                local_files.append(resolved_path)
        
    if args.s3_file:
        s3_files += [f.strip() for f in args.s3_file.split(',')]
    
    total_files = len(local_files) + len(s3_files)
    
    # If neither local nor S3 files were specified, use stdin
    if total_files == 0:
        print("Running validator in streaming mode")
        results = validator.validate_stream(sys.stdin.buffer)
        print(f"Validation results: {results}")
        return
    
    # Initialize activity tracker
    progress_tracker = None
    if not args.quiet:
        progress_tracker = SimpleActivityTracker(total_files)
    
    # Set a reasonable thread count based on file count and system resources
    thread_count = max(1, min(args.threads, total_files, min(32, multiprocessing.cpu_count() * 2)))
    print(f"Using {thread_count} threads for parallel file processing")
    
    # Pre-validate gzip files before starting threads
    if local_files:
        validated_local_files = []
        for file_path in local_files:
            if has_gz_extension(file_path):
                gzip_errors = validate_gzip_format(file_path)
                if gzip_errors:
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
        validator=validator,
        progress_tracker=progress_tracker
    )
    
    # Close progress tracker
    if progress_tracker:
        progress_tracker.close()
    
    # Display summary
    display_summary(all_results)

def process_files_in_parallel(local_files: List[str], s3_files: List[str], 
                              file_format: str, thread_count: int, debug: bool,
                              validator: Any, progress_tracker: SimpleActivityTracker = None) -> List[Dict[str, Any]]:
    """Process multiple files in parallel using a thread pool.
    
    Args:
        local_files: List of local file paths
        s3_files: List of S3 file paths
        file_format: Format of the files
        thread_count: Number of threads to use
        debug: Whether to enable debug output
        validator: Validator instance to use
        progress_tracker: Activity tracker instance or None if tracking is disabled
        
    Returns:
        List of validation results
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = []
        
        # Process local files
        if local_files:
            print(f"Processing {len(local_files)} local files...")
            for file_path in local_files:
                futures.append(
                    executor.submit(
                        validate_local_file,
                        file_path,
                        file_format,
                        debug,
                        validator,  # Pass the validator instance
                        progress_tracker
                    )
                )
                
        # Process S3 files
        if s3_files:
            print(f"Processing {len(s3_files)} S3 files...")
            for s3_path in s3_files:
                futures.append(
                    executor.submit(
                        validate_s3_file,
                        s3_path,
                        file_format,
                        debug,
                        validator,  # Pass the validator instance
                        progress_tracker
                    )
                )
        
        # Collect results as they complete
        all_results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
                # Write each result to validation_progress.log as it completes
                write_result_to_progress_log(result)
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                error_result = {
                    "file_path": "unknown",
                    "error": str(e),
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

if __name__ == "__main__":
    main()
