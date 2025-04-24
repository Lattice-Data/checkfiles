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
import zlib
import io
import signal
import crcmod.predefined
import multiprocessing

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
        with self.lock:
            self.file_status[file_path] = {
                'status': 'Starting...',
                'start_time': datetime.now(),
                'updates': 0,
                'complete': False
            }
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Started: {file_path}")
    
    def update_progress(self, file_path, status=None):
        """Update the status for a specific file."""
        with self.lock:
            if file_path not in self.file_status:
                self.init_file(file_path)
                
            if status is not None:
                self.file_status[file_path]['status'] = status
                self.file_status[file_path]['updates'] += 1
                
                # Only print every other update to reduce output noise
                if self.file_status[file_path]['updates'] % 2 == 0:
                    now = datetime.now()
                    elapsed = (now - self.file_status[file_path]['start_time']).total_seconds()
                    print(f"[{now.strftime('%H:%M:%S')}] {file_path}: {status} (elapsed: {elapsed:.1f}s)")
    
    def complete_file(self, file_path, success, result_summary):
        """Mark a file as completed."""
        with self.lock:
            self.completed += 1
            now = datetime.now()
            
            if file_path in self.file_status:
                self.file_status[file_path]['complete'] = True
                self.file_status[file_path]['success'] = success
                self.file_status[file_path]['result_summary'] = result_summary
                self.file_status[file_path]['end_time'] = now
                
                # Calculate elapsed time
                elapsed = (now - self.file_status[file_path]['start_time']).total_seconds()
                
                # Print completion message with validity status
                if success:
                    valid_status = "Valid" if result_summary.get('valid', False) else "Invalid"
                    print(f"[{now.strftime('%H:%M:%S')}] Completed {file_path}: {valid_status} (took {elapsed:.1f}s)")
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] Failed to process {file_path} (took {elapsed:.1f}s)")
            
            # Print overall progress
            print(f"Progress: {self.completed}/{self.total_files} files processed")
    
    def close(self):
        """Display final summary."""
        end_time = datetime.now()
        total_time = (end_time - self.start_time).total_seconds()
        print(f"\nValidation completed in {total_time:.1f} seconds")

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
    
    return parser.parse_args()

def has_gz_extension(filename):
    """Check if a file has a gzip extension."""
    return filename.lower().endswith(('.gz', '.gzip'))

def stream_s3_file(s3_path, debug=False, progress_tracker=None):
    """Stream a file from S3 using AWS CLI, decompressing if necessary."""
    process = None
    try:
        track_validation_progress(s3_path, progress_tracker, "Initializing S3 stream")
            
        print(f"Attempting to stream file from: {s3_path}")
        
        # Prepare command based on file extension
        is_gzipped = has_gz_extension(s3_path)
        if is_gzipped:
            track_validation_progress(s3_path, progress_tracker, "Setting up decompression")
            print("File has gzip extension, using decompression pipeline")
            cmd = f"aws s3 cp {s3_path} - | gunzip -c"
        else:
            track_validation_progress(s3_path, progress_tracker, "Setting up direct stream")
            print("File does not have gzip extension, streaming directly")
            cmd = f"aws s3 cp {s3_path} -"
            
        print(f"Executing command: {cmd}")
        
        # If in debug mode, first show a preview, then restart the stream
        if debug:
            # Start a process just for preview
            preview_process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Read first chunk for preview
            chunk = preview_process.stdout.read(4096)
            
            if chunk:
                try:
                    preview = chunk[:1000].decode('utf-8', errors='replace')
                    print("\n=== START OF FILE PREVIEW ===")
                    print(preview)
                    print("=== END OF FILE PREVIEW ===\n")
                except Exception as e:
                    print(f"Error decoding preview: {e}")
            else:
                print("No data received from preview stream")
            
            # Terminate the preview process
            preview_process.terminate()
            
            print("Preview complete, starting new stream for validation")
            
        # Start a fresh process for the actual validation
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        track_validation_progress(s3_path, progress_tracker, "Stream ready for validation")
        
        # Return the stdout stream for validation
        return process.stdout
            
    except Exception as e:
        print(f"Error streaming from S3: {e}")
        # Clean up process if it exists
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                pass
        
        # Try to get the stderr output from the subprocess if available
        if process and process.stderr:
            try:
                stderr_output = process.stderr.read().decode('utf-8')
                if stderr_output:
                    print(f"Subprocess error output: {stderr_output}")
            except:
                pass
                
        track_validation_progress(s3_path, progress_tracker, f"Error: {str(e)}")
        return None

def initialize_validator(file_format):
    """Initialize and return the appropriate validator for the given file format.
    
    Args:
        file_format (str): The format of the file to validate (e.g., "fastq")
        
    Returns:
        object: An initialized validator object or None if format is unsupported
        
    Raises:
        ValueError: If the file format is not supported
        ImportError: If there's an issue importing the validator module
    """
    if file_format.lower() == "fastq":
        try:
            from src.validators.fastq import FastqValidator
            return FastqValidator()
        except ImportError as e:
            raise ImportError(f"Error importing FastqValidator: {e}\nMake sure the Rust implementation is properly installed")
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

def track_validation_progress(file_path, progress_tracker, status_message, success=None, results=None):
    """Helper function to handle progress tracking for file validation.
    
    Args:
        file_path (str): Path to the file being processed
        progress_tracker (SimpleActivityTracker): Progress tracker instance or None
        status_message (str): Status message to update
        success (bool, optional): Whether validation was successful
        results (dict, optional): Results of validation if complete
    """
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
    try:
        if progress_tracker:
            progress_tracker.init_file(s3_path)
            
        if validator is None:
            try:
                validator = initialize_validator(file_format)
                if progress_tracker:
                    progress_tracker.update_progress(s3_path, status="Validator created")
            except (ValueError, ImportError) as e:
                raise e
                
        print(f"Validating S3 file: {s3_path}")
        
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Starting S3 streaming")
            
        # Determine if file is gzipped once and reuse this information
        is_gzipped = has_gz_extension(s3_path)
        
        # First pass: Calculate hashes
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Calculating file hashes (1st pass)")
        
        # Initialize hash objects for streaming
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        crc32c_func = crcmod.predefined.Crc('crc-32c')
        
        # First stream to calculate hashes
        stream1 = stream_s3_file(s3_path, debug=debug, progress_tracker=progress_tracker)
        if not stream1:
            error_msg = f"Failed to stream S3 file: {s3_path}"
            print(error_msg)
            
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status="Stream failed")
                progress_tracker.complete_file(s3_path, False, {"error": error_msg})
                
            return {
                "file_path": s3_path,
                "error": error_msg,
                "success": False
            }
        
        # Process first stream to calculate hashes
        while chunk := stream1.read(65536):  # 64kb chunks
            # Update all hashes
            md5_hash.update(chunk)
            sha256_hash.update(chunk)
            crc32c_func.update(chunk)
        
        # Close first stream
        if hasattr(stream1, 'close'):
            stream1.close()
            
        # Second pass: Perform actual validation
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Starting validation (2nd pass)")
            
        # Create second stream for validation
        stream2 = stream_s3_file(s3_path, debug=False, progress_tracker=progress_tracker)
        if not stream2:
            error_msg = f"Failed to create second stream for S3 file: {s3_path}"
            print(error_msg)
            
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status="Second stream failed")
                progress_tracker.complete_file(s3_path, False, {"error": error_msg})
                
            return {
                "file_path": s3_path,
                "error": error_msg,
                "success": False
            }
            
        # Run validation on the second stream
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Running validation")
            
        results = validator.validate_stream(stream2)
        
        # Close second stream
        if hasattr(stream2, 'close'):
            stream2.close()
        
        # Add hash results
        results['md5sum'] = md5_hash.hexdigest()
        results['sha256'] = sha256_hash.hexdigest()
        results['crc32c'] = format(crc32c_func.crcValue, '08x')
        
        # If gzipped, calculate uncompressed md5
        if is_gzipped:
            try:
                # Use consistent subprocess pattern with check_output
                cmd = f'aws s3 cp {s3_path} - | gunzip -c | md5sum'
                output = subprocess.check_output(
                    cmd,
                    shell=True,
                    stderr=subprocess.PIPE
                ).decode('utf-8')
                results['content_md5sum'] = output.split()[0]
            except (subprocess.SubprocessError, IndexError):
                results['content_md5sum'] = None
        
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Validation complete")
            progress_tracker.complete_file(s3_path, True, results)
            
        return {
            "file_path": s3_path,
            "results": results,
            "success": True
        }
        
    except Exception as e:
        error_msg = f"Error validating {s3_path}: {str(e)}"
        print(error_msg)
        
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status=f"Error: {str(e)}")
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
    
    # Initialize activity tracker if not in quiet mode
    progress_tracker = None
    if not args.quiet:
        progress_tracker = SimpleActivityTracker(total_files)
    
    # Report on thread count
    print(f"Using {args.threads} threads for parallel processing")
    
    # Process files in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = []
        
        # Process local files if provided
        if local_files:
            print(f"Processing {len(local_files)} local files...")
            for file_path in local_files:
                futures.append(
                    executor.submit(validate_local_file, file_path, args.file_format, 
                                    args.debug, validator, progress_tracker)
                )
                
        # Process S3 files if provided
        if s3_files:
            print(f"Processing {len(s3_files)} S3 files...")
            for s3_path in s3_files:
                futures.append(
                    executor.submit(validate_s3_file, s3_path, args.file_format, 
                                    args.debug, validator, progress_tracker)
                )
                
        # Collect and store results
        all_results = []
        with open('validation_progress.log', 'w') as progress_file:
            progress_file.write(f"Starting validation of {total_files} files at {datetime.now()}\n")
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                all_results.append(result)
                
                # Log each completion to file
                status = "Valid" if result["success"] and result["results"].get("valid", False) else "Invalid"
                progress_file.write(f"{datetime.now()}: Completed {result['file_path']} - {status}\n")
                progress_file.write(f"Progress: {len(all_results)}/{total_files} ({(len(all_results)/total_files)*100:.1f}%)\n")
                progress_file.flush()  # Ensure it's written immediately
    
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
if __name__ == "__main__":
    main()
