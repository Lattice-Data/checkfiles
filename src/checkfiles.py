#!/usr/bin/env python3

import argparse
import sys
import subprocess
import gzip
import os
import concurrent.futures
import threading
from datetime import datetime

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
    parser.add_argument('-t', '--threads', type=int, default=4, 
                        help='Number of threads for parallel processing (default: 4)')
    parser.add_argument('-q', '--quiet', action='store_true', 
                        help='Suppress progress indicators and only show final results')
    
    return parser.parse_args()

def has_gz_extension(filename):
    """Check if a file has a gzip extension."""
    return filename.lower().endswith(('.gz', '.gzip'))

def stream_s3_file(s3_path, debug=False, progress_tracker=None):
    """Stream a file from S3 using AWS CLI, decompressing if necessary."""
    try:
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Initializing S3 stream")
            
        print(f"Attempting to stream file from: {s3_path}")
        
        # Prepare command based on file extension
        is_gzipped = has_gz_extension(s3_path)
        if is_gzipped:
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status="Setting up decompression")
            print("File has gzip extension, using decompression pipeline")
            cmd = f"aws s3 cp {s3_path} - | gunzip -c"
        else:
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status="Setting up direct stream")
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
        
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Stream ready for validation")
            
        return process.stdout
            
    except Exception as e:
        print(f"Error streaming from S3: {e}")
        # Try to get the stderr output from the subprocess if available
        if 'process' in locals():
            stderr_output = process.stderr.read().decode('utf-8')
            if stderr_output:
                print(f"Subprocess error output: {stderr_output}")
                
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status=f"Error: {str(e)}")
            
        return None

def validate_local_file(file_path, file_format, debug=False, validator=None, progress_tracker=None):
    """Validate a local file."""
    try:
        if progress_tracker:
            progress_tracker.init_file(file_path)  # Ensure we initialize tracking
            progress_tracker.update_progress(file_path, status="Initializing")
            
        if validator is None:
            if file_format.lower() == "fastq":
                from src.validators.fastq import FastqValidator
                validator = FastqValidator()
                
                if progress_tracker:
                    progress_tracker.update_progress(file_path, status="Validator created")
            else:
                raise ValueError(f"Unsupported file format: {file_format}")
                
        print(f"Validating local file: {file_path}")
        
        if progress_tracker:
            progress_tracker.update_progress(file_path, status="Reading file")
        
        # Check if local file is gzipped
        if has_gz_extension(file_path):
            if progress_tracker:
                progress_tracker.update_progress(file_path, status="Decompressing")
                
            with gzip.open(file_path, 'rb') as f:
                if progress_tracker:
                    progress_tracker.update_progress(file_path, status="Running validation")
                    
                results = validator.validate_stream(f)
        else:
            if progress_tracker:
                progress_tracker.update_progress(file_path, status="Running validation")
                
            results = validator.validate_file(file_path)
            
        if progress_tracker:
            progress_tracker.update_progress(file_path, status="Validation complete")
            progress_tracker.complete_file(file_path, True, results)
            
        return {
            "file_path": file_path,
            "results": results,
            "success": True
        }
        
    except Exception as e:
        error_msg = f"Error validating {file_path}: {str(e)}"
        print(error_msg)
        
        if progress_tracker:
            progress_tracker.update_progress(file_path, status=f"Error: {str(e)}")
            progress_tracker.complete_file(file_path, False, {"error": str(e)})
            
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
            if file_format.lower() == "fastq":
                from src.validators.fastq import FastqValidator
                validator = FastqValidator()
                
                if progress_tracker:
                    progress_tracker.update_progress(s3_path, status="Validator created")
            else:
                raise ValueError(f"Unsupported file format: {file_format}")
                
        print(f"Validating S3 file: {s3_path}")
        
        if progress_tracker:
            progress_tracker.update_progress(s3_path, status="Starting S3 streaming")
            
        stream = stream_s3_file(s3_path, debug=debug, progress_tracker=progress_tracker)
        if stream:
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status="Running validation")
                
            results = validator.validate_stream(stream)
            
            if progress_tracker:
                progress_tracker.update_progress(s3_path, status="Validation complete")
                progress_tracker.complete_file(s3_path, True, results)
                
            return {
                "file_path": s3_path,
                "results": results,
                "success": True
            }
        else:
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

def main():
    args = parse_arguments()
    
    # Check if file format is supported
    if not args.file_format:
        print("Please specify a file format using the -f/--file-format option")
        return
        
    # Initialize validator
    validator = None
    if args.file_format.lower() == "fastq":
        try:
            from src.validators.fastq import FastqValidator
            validator = FastqValidator()
        except ImportError as e:
            print(f"Error importing FastqValidator: {e}")
            print("Make sure the Rust implementation is properly installed")
            return
    else:
        print(f"Unsupported file format: {args.file_format}")
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
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            all_results.append(result)
    
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

if __name__ == "__main__":
    main()
