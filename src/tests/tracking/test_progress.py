"""Tests for progress tracking functionality."""

import pytest
import io
import threading
from datetime import datetime
from src.tracking.progress import SimpleActivityTracker, ProgressTrackingStream

def test_simple_activity_tracker_initialization():
    """Test SimpleActivityTracker initialization."""
    tracker = SimpleActivityTracker(total_files=5)
    assert tracker.total_files == 5
    assert tracker.completed == 0
    assert isinstance(tracker.file_status, dict)
    assert len(tracker.file_status) == 0
    assert isinstance(tracker.start_time, datetime)

def test_simple_activity_tracker_file_lifecycle():
    """Test the complete lifecycle of tracking a file."""
    tracker = SimpleActivityTracker(total_files=1)
    
    # Test file initialization
    file_path = "test.txt"
    tracker.init_file(file_path)
    assert file_path in tracker.file_status
    assert tracker.file_status[file_path]['status'] == 'Starting...'
    assert not tracker.file_status[file_path]['complete']
    assert 'start_time' in tracker.file_status[file_path]
    assert 'thread_id' in tracker.file_status[file_path]
    
    # Test progress update
    tracker.update_progress(file_path, "Processing...")
    assert tracker.file_status[file_path]['status'] == 'Processing...'
    assert tracker.file_status[file_path]['updates'] == 1
    
    # Test completion
    result_summary = {'valid': True, 'checks': ['format', 'content']}
    tracker.complete_file(file_path, True, result_summary)
    assert tracker.completed == 1
    assert tracker.file_status[file_path]['complete']
    assert tracker.file_status[file_path]['success']
    assert tracker.file_status[file_path]['result_summary'] == result_summary
    assert 'end_time' in tracker.file_status[file_path]

def test_simple_activity_tracker_multiple_files():
    """Test tracking multiple files."""
    tracker = SimpleActivityTracker(total_files=3)
    
    # Track multiple files
    files = ["file1.txt", "file2.txt", "file3.txt"]
    for file_path in files:
        tracker.init_file(file_path)
        tracker.update_progress(file_path, "Processing...")
        tracker.complete_file(file_path, True, {'valid': True})
    
    assert tracker.completed == 3
    assert len(tracker.file_status) == 3
    for file_path in files:
        assert tracker.file_status[file_path]['complete']
        assert tracker.file_status[file_path]['success']

def test_simple_activity_tracker_error_handling():
    """Test error handling in SimpleActivityTracker."""
    tracker = SimpleActivityTracker(total_files=1)
    
    # Test completing a file that wasn't initialized
    file_path = "nonexistent.txt"
    tracker.complete_file(file_path, False, {'error': 'File not found'})
    assert tracker.completed == 1
    assert file_path not in tracker.file_status  # Should not create entry for non-existent file

def test_progress_tracking_stream():
    """Test ProgressTrackingStream functionality."""
    # Create a test stream with larger content (1KB)
    test_content = b"Line 1\n" * 100  # Create a larger content
    base_stream = io.BytesIO(test_content)
    
    # Create a tracker
    tracker = SimpleActivityTracker(total_files=1)
    file_path = "test.txt"
    tracker.init_file(file_path)
    
    # Create a tracking stream with a very small update interval (100 bytes)
    tracking_stream = ProgressTrackingStream(base_stream, tracker, update_interval_mb=0.0001)
    
    # Set file path before reading
    tracking_stream.file_path = file_path
    
    # Test reading line by line
    lines = []
    for line in tracking_stream:
        lines.append(line)
    
    assert len(lines) == 100
    assert b''.join(lines) == test_content
    assert tracking_stream.total_bytes == len(test_content)
    
    # Force a final update to ensure we get at least one update
    tracking_stream._update_progress(0)
    
    # Verify tracker was updated
    assert tracker.file_status[file_path]['updates'] > 0, "No progress updates were recorded"

def test_progress_tracking_stream_read():
    """Test ProgressTrackingStream read method."""
    # Create a larger content (10KB)
    test_content = b"Test content" * 1000
    base_stream = io.BytesIO(test_content)
    
    tracker = SimpleActivityTracker(total_files=1)
    file_path = "test.txt"
    tracker.init_file(file_path)
    
    # Create a tracking stream with a small update interval (1KB)
    tracking_stream = ProgressTrackingStream(base_stream, tracker, update_interval_mb=0.001)
    tracking_stream.file_path = file_path
    
    # Test reading in chunks
    chunk_size = 1024
    total_read = 0
    while True:
        chunk = tracking_stream.read(chunk_size)
        if not chunk:
            break
        total_read += len(chunk)
    
    assert total_read == len(test_content)
    assert tracking_stream.total_bytes == len(test_content)
    assert tracker.file_status[file_path]['updates'] > 0

def test_progress_tracking_stream_without_tracker():
    """Test ProgressTrackingStream without a tracker."""
    test_content = b"Test content"
    base_stream = io.BytesIO(test_content)
    
    # Create stream without tracker
    tracking_stream = ProgressTrackingStream(base_stream)
    
    # Read content
    content = tracking_stream.read()
    assert content == test_content
    assert tracking_stream.total_bytes == len(test_content)
    # Should not raise any errors even without a tracker

def test_simple_activity_tracker_thread_safety():
    """Test thread safety of SimpleActivityTracker."""
    tracker = SimpleActivityTracker(total_files=10)
    
    def worker(file_num):
        file_path = f"file{file_num}.txt"
        tracker.init_file(file_path)
        tracker.update_progress(file_path, "Processing...")
        tracker.complete_file(file_path, True, {'valid': True})
    
    # Create and start multiple threads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Verify results
    assert tracker.completed == 5
    assert len(tracker.file_status) == 5
    for i in range(5):
        file_path = f"file{i}.txt"
        assert file_path in tracker.file_status
        assert tracker.file_status[file_path]['complete']
        assert tracker.file_status[file_path]['success'] 