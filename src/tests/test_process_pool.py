"""
Simplified test to debug issues with ProcessPoolExecutor.
"""
import sys
import os
import pytest
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch, MagicMock

# Add the parent directory to path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def simple_function(x):
    """A simple function that returns its input."""
    return x

def test_process_pool_executor_basic():
    """Test basic functionality of ProcessPoolExecutor without mocking."""
    with ProcessPoolExecutor(max_workers=2) as executor:
        future = executor.submit(simple_function, 42)
        result = future.result()
        assert result == 42

def test_process_pool_executor_with_mock():
    """Test ProcessPoolExecutor with mocking to check if that's causing issues."""
    # Create a simple mock
    mock_executor = MagicMock()
    mock_future = MagicMock()
    mock_future.result.return_value = 42
    mock_executor.__enter__.return_value.submit.return_value = mock_future
    
    # Patch the exact location where ProcessPoolExecutor is imported in this module
    # The issue was using the wrong import path for patching
    with patch('src.tests.test_process_pool.ProcessPoolExecutor', return_value=mock_executor):
        with ProcessPoolExecutor(max_workers=2) as executor:
            future = executor.submit(simple_function, 42)
            result = future.result()
            assert result == 42
            
        # Verify the mock was used correctly
        mock_executor.__enter__.assert_called_once()

if __name__ == "__main__":
    # Allow running this test directly
    pytest.main(["-xvs", __file__]) 