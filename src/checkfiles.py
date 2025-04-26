#!/usr/bin/env python3

import argparse
import sys
import subprocess
import gzip
import os
import concurrent.futures
import threading
from datetime import datetime
import hashlib
import io
import crcmod.predefined
import multiprocessing
import logging
import queue
import shlex
import zlib
import time
import tempfile

# Create logs directory in current working directory if it doesn't exist
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'checkfiles_debug.log')

# Configure logging to a file for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='w'
)
logger = logging.getLogger(__name__)
logger.debug(f"Logging to: {log_file}")

# Print debugging information
logger.debug(f"Python version: {sys.version}")
logger.debug(f"Python path: {sys.path}")
logger.debug(f"Current directory: {os.getcwd()}")

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
    
class SimpleActivityTracker:
    """Simple activity tracker for validation processes."""
    
    def __init__(self, total_files):
        self.total_files = total_files
        self.completed = 0
        self.lock = threading.Lock()
        self.file_status = {}
        self.start_time = datetime.now()
        print(f"Starting validation of {total_files} files at {self.start_time.strftime('%H:%M:%S')}")
    
    def init_file(self, file_path):
        """Initialize tracking for a new file."""
        thread_id = threading.get_ident()
        with self.lock:
            self.file_status[file_path] = {
                'status': 'Starting...',
                'start_time': datetime.now(),
                'updates': 0,
                'complete': False,
                'thread_id': thread_id,
                'thread_name': f"Thread-{thread_id % 1000:03d}"  # Last 3 digits of thread ID for readability
            }
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [T-{thread_id % 1000:03d}] Started: {file_path}")
    
    def update_progress(self, file_path, status=None):
        """Update the status for a specific file."""
        with self.lock:
            if file_path not in self.file_status:
                self.init_file(file_path)
                
            if status is not None:
                self.file_status[file_path]['status'] = status
                self.file_status[file_path]['updates'] += 1
                thread_name = self.file_status[file_path]['thread_name']
                
                # Only print every other update to reduce output noise
                if self.file_status[file_path]['updates'] % 2 == 0:
                    now = datetime.now()
                    elapsed = (now - self.file_status[file_path]['start_time']).total_seconds()
                    print(f"[{now.strftime('%H:%M:%S')}] [{thread_name}] {file_path}: {status} (elapsed: {elapsed:.1f}s)")
    
    def complete_file(self, file_path, success, result_summary):
        """Mark a file as completed."""
        with self.lock:
            self.completed += 1
            now = datetime.now()
            
            if file_path in self.file_status:
                thread_name = self.file_status[file_path]['thread_name']
                self.file_status[file_path]['complete'] = True
                self.file_status[file_path]['success'] = success
                self.file_status[file_path]['result_summary'] = result_summary
                self.file_status[file_path]['end_time'] = now
                
                # Calculate elapsed time
                elapsed = (now - self.file_status[file_path]['start_time']).total_seconds()
                
                # Print completion message with validity status and thread info
                if success:
                    valid_status = "Valid" if result_summary.get('valid', False) else "Invalid"
                    print(f"[{now.strftime('%H:%M:%S')}] [{thread_name}] Completed {file_path}: {valid_status} (took {elapsed:.1f}s)")
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] [{thread_name}] Failed to process {file_path} (took {elapsed:.1f}s)")
            
            # Print overall progress
            print(f"Progress: {self.completed}/{self.total_files} files processed")
    
    def close(self):
        """Display final summary."""
        end_time = datetime.now()
        total_time = (end_time - self.start_time).total_seconds()
        print(f"\nValidation completed in {total_time:.1f} seconds")
        
        # Add thread distribution summary
        thread_counts = {}
        for path, info in self.file_status.items():
            thread_name = info.get('thread_name', 'Unknown')
            thread_counts[thread_name] = thread_counts.get(thread_name, 0) + 1
        
        print("\nThread distribution:")
        for thread, count in thread_counts.items():
            print(f"  {thread}: {count} file(s)")

def parse_arguments():
    # Get the number of available CPUs for default thread count
    default_threads = multiprocessing.cpu_count()
    
    parser = argparse.ArgumentParser(
        description='Checkfiles utility - validates file formats like FASTQ. Accepts files from local paths, S3, or stdin.',
        epilog='''Examples:
  # Validate a single local file
  ./src/checkfiles.py -f fastq -l path/to/file.fastq.gz
  
  # Validate multiple S3 files
  ./src/checkfiles.py -f fastq -s3 s3://bucket/file1.fastq.gz,s3://bucket/file2.fastq.gz
  
  # Validate from stdin (pipe input)
  cat file.fastq | ./src/checkfiles.py -f fastq
  # or
  aws s3 cp s3://bucket/file.fastq.gz - | gunzip -c | ./src/checkfiles.py -f fastq
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-s3', '--s3-file', help='Specify S3 file(s) as comma-separated paths')
    parser.add_argument('-l', '--local-file', help='Specify local file(s) to validate as comma-separated paths')
    parser.add_argument('-f', '--file-format', help='Specify the file format (e.g., fastq)')
    parser.add_argument('-s', '--stream', action='store_true', default=True, 
                        help='Use streaming mode for validation (default: True)')
    parser.add_argument('-d', '--debug', action='store_true', 
                        help='Enable debug output')
    parser.add_argument('-t', '--threads', type=int, default=default_threads, 
                        help=f'Number of threads for parallel processing (default: {default_threads}, based on CPU count)')
    parser.add_argument('-q', '--quiet', action='store_true', 
                        help='Suppress progress indicators and only show final results')
    parser.add_argument('--log-file', 
                        help='Path to log file (default: ./logs/checkfiles_debug.log)')
    
    return parser.parse_args()

def has_gz_extension(filename):
    """Check if a file has a gzip extension."""
    return filename.lower().endswith(('.gz', '.gzip'))

def initialize_validator(file_format):
    """Initialize and return the appropriate validator for the given file format."""
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

def track_validation_progress(file_path, progress_tracker, status_message, success=None, results=None):
    """Helper function to handle progress tracking for file validation."""
    if not progress_tracker:
        return
        
    if status_message:
        progress_tracker.update_progress(file_path, status=status_message)
        
    if success is not None and results is not None:
        progress_tracker.complete_file(file_path, success, results)

def validate_local_file(file_path, file_format, debug=False, validator=None, progress_tracker=None):
    """Validate a local file."""
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

def validate_s3_file(s3_path, file_format, debug=False, validator=None, progress_tracker=None):
    """Validate an S3 file."""
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
        
        # Create command based on file type
        s3_path_escaped = shlex.quote(s3_path)
        if has_gz_extension(s3_path):
            cmd = f"aws s3 cp {s3_path_escaped} - | gunzip -c"
            track_validation_progress(s3_path, progress_tracker, "Setting up decompression stream")
        else:
            cmd = f"aws s3 cp {s3_path_escaped} -"
            track_validation_progress(s3_path, progress_tracker, "Setting up direct stream")
        
        # Start the subprocess with a smaller buffer to prevent memory issues
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=262144  # 256KB buffer
        )
        
        # Check if process started successfully
        if process.poll() is not None:
            stderr = process.stderr.read().decode('utf-8')
            raise RuntimeError(f"Failed to start S3 stream: {stderr}")
        
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Stream established")
        
        # Initialize hash objects
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        crc32c_func = crcmod.predefined.Crc('crc-32c')
        
        # Create a temporary file for validation
        with tempfile.TemporaryFile() as temp_file:
            total_bytes = 0
            chunk_size = 262144  # 256KB chunks for better memory management
            
            # Read and process data in chunks
            while True:
                chunk = process.stdout.read(chunk_size)
                if not chunk:
                    break
                
                # Update hashes
                md5_hash.update(chunk)
                sha256_hash.update(chunk)
                crc32c_func.update(chunk)
                
                # Write to temp file
                temp_file.write(chunk)
                
                total_bytes += len(chunk)
                if progress_tracker and total_bytes % (1024*1024) == 0:  # Update every 1MB
                    progress_tracker.update_progress(
                        s3_path, 
                        status=f"Processed {total_bytes/1024/1024:.1f} MB"
                    )
            
            # Check if process ended successfully
            if process.poll() is not None and process.returncode != 0:
                stderr = process.stderr.read().decode('utf-8')
                raise RuntimeError(f"S3 stream failed: {stderr}")
            
            # Rewind temp file for validation
            temp_file.seek(0)
            
            # Run validation
            logger.debug("Starting FASTQ validation")
            results = validator.validate_stream(temp_file)
            logger.debug("FASTQ validation completed")
            
            # Add hash results
            results['md5sum'] = md5_hash.hexdigest()
            results['sha256'] = sha256_hash.hexdigest()
            results['crc32c'] = format(crc32c_func.crcValue, '08x')
        
        # Clean up process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception as term_error:
                logger.error(f"Error terminating process: {str(term_error)}")
        
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
        
        # Clean up
        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception as term_error:
                logger.error(f"Error terminating process: {str(term_error)}")
        
        if progress_tracker:
            progress_tracker.complete_file(s3_path, False, {"error": str(e)})
        
        return {
            "file_path": s3_path,
            "error": error_msg,
            "success": False
        }

def validate_gzip_format(file_path):
    """
    Validate if a file is properly gzipped by checking magic number and basic header structure.
    Does not read the entire file to avoid performance issues with large files.
    Handles both local files and S3 files.
    
    Args:
        file_path (str): Path to the file to check. Can be local path or s3:// URL
        
    Returns:
        dict: Empty if valid, contains error message if invalid
    """
    error = {}
    try:
        if file_path.startswith('s3://'):
            # For S3 files, use aws s3 cp to stream just the first few bytes
            cmd = f"aws s3 cp {file_path} - --range 0-1"  # Get first 2 bytes for magic number
            try:
                # Use consistent subprocess pattern with check_output
                magic_number = subprocess.check_output(
                    cmd, 
                    shell=True, 
                    stderr=subprocess.PIPE
                )[:2]
                
                if magic_number != b'\x1f\x8b':
                    error = {'gzip_error': 'File does not have valid gzip magic number'}
                    return error
                
                # Try reading a bit more to verify header structure
                cmd = f"aws s3 cp {file_path} - --range 0-9 | gunzip -c"
                subprocess.check_output(
                    cmd, 
                    shell=True, 
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError as e:
                error = {'gzip_error': f'File has invalid gzip header structure: {e.stderr.decode("utf-8")}'}
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
                    
    except (IsADirectoryError, FileNotFoundError) as e:
        error = {'gzip_error': str(e)}
    except Exception as e:
        error = {'gzip_error': f'Unexpected error checking gzip format: {str(e)}'}
        
    return error
    
def main():
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
    # Use min(CPU cores * 2, files, 32) but at least 1
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
                        args.file_format,
                        args.debug,
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
                        args.file_format,
                        args.debug,
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
    
    # Close progress tracker
    if progress_tracker:
        progress_tracker.close()
    
    # Display summary
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

        print("+++++++++++++++++++++")
        print(result)
        print("+++++++++++++++++++++")

def stream_s3_file(s3_path, decompress=None):
    """
    Create a stream from an S3 file using AWS CLI.
    
    Args:
        s3_path (str): S3 path in the format s3://bucket/key
        decompress (bool, optional): Whether to decompress the file. If None, will be determined by file extension.
    
    Returns:
        subprocess.Popen: A process with stdout pipe containing the file content
    """
    import subprocess
    import shlex
    
    # Determine if we should decompress based on file extension if not specified
    if decompress is None:
        decompress = has_gz_extension(s3_path)
    
    # Escape the s3 path for shell safety
    s3_path_escaped = shlex.quote(s3_path)
    
    if decompress:
        cmd = f"aws s3 cp {s3_path_escaped} - | gunzip -c"
    else:
        cmd = f"aws s3 cp {s3_path_escaped} -"
    
    # Start the subprocess
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1048576  # 1MB buffer
    )
    
    # Check if process started successfully
    if process.poll() is not None:
        stderr = process.stderr.read().decode('utf-8')
        raise RuntimeError(f"Failed to start S3 stream: {stderr}")
    
    return process.stdout

if __name__ == "__main__":
    main()
