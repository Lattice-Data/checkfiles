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
from typing import List, Dict, Any

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
        logger = logging.getLogger(__name__)
        logger.debug(f"Logging redirected to: {args.log_file}")
    
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
    
    if args.local_file:
        local_files = [f.strip() for f in args.local_file.split(',')]
        
    if args.s3_file:
        s3_files = [f.strip() for f in args.s3_file.split(',')]
    
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
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                all_results.append({
                    "file_path": "unknown",
                    "error": str(e),
                    "success": False
                })
    
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
            if not result["results"]["valid"]:
                print(f"  Errors: {result['results'].get('errors', {})}")
            if result["results"].get("warnings"):
                print(f"  Warnings: {result['results'].get('warnings', {})}")
        else:
            print(f"{result['file_path']}: Failed - {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()
