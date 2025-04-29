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
        print(f"Starting validation of {total_files} files at {self.start_time}")
    
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
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [T-{thread_id % 1000:03d}] Started: {file_path}")
    
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
                
                # Print every single update without filtering
                now = datetime.now()
                elapsed = (now - self.file_status[file_path]['start_time']).total_seconds()
                print(f"{now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [{thread_name}] {file_path}: {status} (elapsed: {elapsed:.1f}s, updates: {self.file_status[file_path]['updates']})")
    
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
                total_updates = self.file_status[file_path]['updates']
                
                # Print completion message with validity status and thread info
                if success:
                    valid_status = "Valid" if result_summary.get('valid', False) else "Invalid"
                    print(f"{now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [{thread_name}] Completed {file_path}: {valid_status} (took {elapsed:.1f}s, total updates: {total_updates})")
                else:
                    print(f"{now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [{thread_name}] Failed to process {file_path} (took {elapsed:.1f}s, total updates: {total_updates})")
            
            # Print overall progress
            print(f"Progress: {self.completed}/{self.total_files} ({self.completed/self.total_files*100:.1f}%)")
    
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

class ProgressTrackingStream:
    """Stream wrapper that tracks reading progress for large file processing."""
    
    def __init__(self, stream, tracker=None, update_interval_mb=5):
        """Initialize a tracking stream.
        
        Args:
            stream: The underlying stream to read from
            tracker: Optional progress tracker to update
            update_interval_mb: Progress update interval in megabytes (default: 5)
        """
        self.stream = stream
        self.tracker = tracker
        self.file_path = None  # Will be set by the caller if needed
        self.total_bytes = 0
        self.last_update = 0
        self.update_count = 0
        self.update_interval_bytes = update_interval_mb * 1024 * 1024  # Convert MB to bytes
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} Created tracking stream for file: {self.file_path}")
        
    def __iter__(self):
        """Make this stream iterable for line-by-line processing."""
        return self
        
    def __next__(self):
        """Get the next line from the stream."""
        data = self.stream.readline()
        if not data:
            raise StopIteration
        
        # Track progress
        self.total_bytes += len(data)
        self._update_progress(len(data))
        return data
        
    def read(self, size=-1):
        """Read data from the stream and track progress.
        
        Args:
            size: Number of bytes to read, -1 for all
            
        Returns:
            Binary data read from the stream
        """
        data = self.stream.read(size)
        if data:
            self.total_bytes += len(data)
            self._update_progress(len(data))
        return data
        
    def _update_progress(self, bytes_read):
        """Update progress tracking.
        
        Args:
            bytes_read: Number of bytes just read
        """
        if not self.tracker:
            return
            
        # Update progress based on configured interval
        if self.total_bytes - self.last_update >= self.update_interval_bytes:
            self.update_count += 1
            if self.file_path:
                self.tracker.update_progress(
                    self.file_path,
                    status=f"Processed {self.total_bytes/1024/1024:.1f} MB (update #{self.update_count})"
                )
            else:
                # No file path available, so no update possible with SimpleActivityTracker
                pass
            self.last_update = self.total_bytes
        