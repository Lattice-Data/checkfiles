#!/usr/bin/env python3
"""
Test script to verify that multiprocessing serialization works correctly.

Usage:
    python test_serialization.py
"""

import os
import sys
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import threading
import pickle

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    # Import the progress tracker
    from src.tracking.progress import SimpleActivityTracker
    print("Successfully imported SimpleActivityTracker")
except ImportError as e:
    print(f"Failed to import SimpleActivityTracker: {e}")
    sys.exit(1)

def worker_function(file_path, tracker=None):
    """
    Worker function that would be called in a process pool.
    
    Args:
        file_path: Path to a file to process
        tracker: SimpleActivityTracker instance or None
        
    Returns:
        Dict with results
    """
    print(f"Worker processing {file_path}")
    
    # Simulate some work
    if tracker:
        try:
            tracker.init_file(file_path)
            tracker.update_progress(file_path, "Starting work")
            time.sleep(0.5)
            tracker.update_progress(file_path, "50% complete")
            time.sleep(0.5)
            result = {"success": True, "file_path": file_path, "results": {"valid": True}}
            tracker.complete_file(file_path, True, {"valid": True})
            print(f"Worker completed {file_path} with tracker")
        except Exception as e:
            print(f"Error with tracker in worker: {e}")
            result = {"success": False, "file_path": file_path, "error": str(e)}
    else:
        # Simulation without tracker
        time.sleep(1)
        result = {"success": True, "file_path": file_path, "results": {"valid": True}}
        print(f"Worker completed {file_path} without tracker")
        
    return result

def test_pickle_tracker():
    """
    Test if a SimpleActivityTracker can be pickled directly.
    
    Returns:
        bool: Whether the test succeeded
    """
    print("\n==== Testing direct pickling of SimpleActivityTracker ====")
    tracker = SimpleActivityTracker(5)
    
    try:
        # Test if the tracker can be pickled
        pickle_data = pickle.dumps(tracker)
        print(f"Successfully pickled tracker: {len(pickle_data)} bytes")
        
        # Try to unpickle it
        unpickled = pickle.loads(pickle_data)
        print(f"Successfully unpickled tracker: {type(unpickled)}")
        
        # Try to use the unpickled tracker
        unpickled.init_file("test_file.txt")
        unpickled.update_progress("test_file.txt", "Testing after unpickling")
        unpickled.complete_file("test_file.txt", True, {"valid": True})
        print("Successfully used unpickled tracker")
        
        return True
    except Exception as e:
        print(f"Error pickling/unpickling tracker: {e}")
        return False

def test_multiprocessing():
    """
    Test using a SimpleActivityTracker with multiprocessing.
    
    Method 1: Try to pass the tracker to worker processes (should fail)
    Method 2: Don't pass the tracker (should work)
    """
    print("\n==== Testing SimpleActivityTracker with multiprocessing ====")
    
    # Create a list of test files
    test_files = [f"file_{i}.txt" for i in range(5)]
    
    # === Method 1: Try to pass the tracker to workers (will likely fail) ===
    print("\n--- Method 1: Passing tracker to workers (expected to fail) ---")
    try:
        tracker = SimpleActivityTracker(len(test_files))
        results = []
        
        with ProcessPoolExecutor(max_workers=2) as executor:
            futures = []
            for file_path in test_files:
                # Try to pass the tracker to the worker
                futures.append(
                    executor.submit(worker_function, file_path, tracker)
                )
                
            # Collect results
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"Error in worker process: {e}")
                    
        print(f"Method 1 completed with {len(results)} results")
    except Exception as e:
        print(f"Method 1 failed: {e}")
    
    # === Method 2: Don't pass the tracker to workers (should work) ===
    print("\n--- Method 2: Not passing tracker to workers (should work) ---")
    try:
        tracker = SimpleActivityTracker(len(test_files))
        results = []
        
        with ProcessPoolExecutor(max_workers=2) as executor:
            futures = []
            for file_path in test_files:
                # Don't pass the tracker to the worker
                futures.append(
                    executor.submit(worker_function, file_path, None)
                )
                
            # Collect results
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Update tracker in the main process
                    tracker.init_file(result["file_path"])
                    if result["success"]:
                        tracker.complete_file(
                            result["file_path"], 
                            True, 
                            result.get("results", {})
                        )
                    else:
                        tracker.complete_file(
                            result["file_path"], 
                            False, 
                            {"error": result.get("error", "Unknown error")}
                        )
                except Exception as e:
                    print(f"Error in worker process: {e}")
                    
        print(f"Method 2 completed with {len(results)} results")
        tracker.close()
    except Exception as e:
        print(f"Method 2 failed: {e}")

if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"Process count: {multiprocessing.cpu_count()}")
    
    # Run the direct pickle test
    pickle_success = test_pickle_tracker()
    
    # Run the multiprocessing test
    test_multiprocessing()
    
    # Final summary
    print("\n==== Summary ====")
    print(f"Direct pickling test: {'SUCCESS' if pickle_success else 'FAILED'}")
    print("Note: Even with __getstate__ and __setstate__ implementations, passing a")
    print("SimpleActivityTracker directly to worker processes may still fail because")
    print("of other non-picklable attributes. It's best to keep the tracker in the main")
    print("process and update it with results from workers.") 