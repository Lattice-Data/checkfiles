"""Tests for path translation functionality."""

import os
import pytest
from unittest.mock import patch
from src.path_translator import (
    translate_host_path_to_container,
    is_s3_uri,
    resolve_path
)

def test_is_s3_uri():
    """Test the is_s3_uri function with various paths."""
    # Test valid S3 URIs
    assert is_s3_uri("s3://bucket/key") is True
    assert is_s3_uri("s3://my-bucket/path/to/file.txt") is True
    assert is_s3_uri("s3://") is True
    
    # Test invalid paths
    assert is_s3_uri("/path/to/file.txt") is False
    assert is_s3_uri("file.txt") is False
    assert is_s3_uri("") is False
    assert is_s3_uri("s3:/invalid") is False

def test_translate_host_path_to_container():
    """Test the translate_host_path_to_container function."""
    # Test with HOST_HOME environment variable
    with patch.dict('os.environ', {'HOST_HOME': '/home/user'}, clear=True):
        # Test direct mapping through volume mount
        assert translate_host_path_to_container('/home/user/file.txt') == '/home/user/file.txt'
        
        # Test project directory mappings
        assert translate_host_path_to_container('/src/utils/helpers.py') == '/app/src/utils/helpers.py'
        assert translate_host_path_to_container('/test_data/sample.txt') == '/app/test_data/sample.txt'
        assert translate_host_path_to_container('/logs/app.log') == '/app/logs/app.log'
        
        # Test paths that can't be translated
        assert translate_host_path_to_container('/other/path/file.txt') == '/other/path/file.txt'
    
    # Test without HOST_HOME environment variable
    with patch.dict('os.environ', {}, clear=True):
        assert translate_host_path_to_container('/home/user/file.txt') is None

def test_resolve_path():
    """Test the resolve_path function with various path types."""
    # Test S3 URIs
    assert resolve_path("s3://bucket/key") == "s3://bucket/key"
    assert resolve_path("s3://my-bucket/path/to/file.txt") == "s3://my-bucket/path/to/file.txt"
    
    # Test relative paths
    with patch('os.path.abspath', return_value='/absolute/path/file.txt'):
        assert resolve_path("relative/path/file.txt") == '/absolute/path/file.txt'
    
    # Test absolute paths that need translation
    with patch.dict('os.environ', {'HOST_HOME': '/home/user'}, clear=True), \
         patch('os.path.exists', side_effect=lambda p: p == '/app/src/utils/helpers.py'):
        assert resolve_path('/src/utils/helpers.py') == '/app/src/utils/helpers.py'
    
    # Test absolute paths that don't need translation
    with patch('os.path.exists', return_value=True):
        assert resolve_path('/app/src/utils/helpers.py') == '/app/src/utils/helpers.py'
    
    # Test paths that can't be resolved
    with patch('os.path.exists', return_value=False):
        assert resolve_path('/nonexistent/path/file.txt') == '/nonexistent/path/file.txt'

def test_resolve_path_with_mixed_paths():
    """Test resolve_path with a mix of different path types."""
    # Test with HOST_HOME environment variable
    with patch.dict('os.environ', {'HOST_HOME': '/home/user'}, clear=True), \
         patch('os.path.exists', side_effect=lambda p: p in ['/app/src/utils/helpers.py', '/app/test_data/sample.txt']):
        
        # Test various path types
        assert resolve_path("s3://bucket/key") == "s3://bucket/key"  # S3 URI
        assert resolve_path('/src/utils/helpers.py') == '/app/src/utils/helpers.py'  # Host path
        assert resolve_path('/app/test_data/sample.txt') == '/app/test_data/sample.txt'  # Container path
        assert resolve_path('relative/path.txt') == os.path.abspath('relative/path.txt')  # Relative path
        assert resolve_path('/nonexistent/path.txt') == '/nonexistent/path.txt'  # Unresolvable path 