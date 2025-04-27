"""Progress tracking for file validation operations."""

import threading
from datetime import datetime
from typing import Dict, Any, Optional

class SimpleActivityTracker:
    """Simple activity tracker for validation processes."""
    
    def __init__(self, total_files: int):
        """Initialize a new activity tracker.
        
        Args:
            total_files: The total number of files to process
        """
        self.total_files = total_files
        self.completed = 0
        self.lock = threading.Lock()
        self.file_status: Dict[str, Dict[str, Any]] = {}
        self.start_time = datetime.now()
        print(f"Starting validation of {total_files} files at {self.start_time.strftime('%H:%M:%S')}")
    
    def init_file(self, file_path: str) -> None:
        """Initialize tracking for a new file.
        
        Args:
            file_path: Path to the file being processed
        """
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
    
    def update_progress(self, file_path: str, status: Optional[str] = None) -> None:
        """Update the status for a specific file.
        
        Args:
            file_path: Path to the file being processed
            status: New status message
        """
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
    
    def complete_file(self, file_path: str, success: bool, result_summary: Dict[str, Any]) -> None:
        """Mark a file as completed.
        
        Args:
            file_path: Path to the file being processed
            success: Whether the processing was successful
            result_summary: Summary of the validation results
        """
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
    
    def close(self) -> None:
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