"""
Test configuration for pytest.

This module provides:
1. Custom pytest markers
2. Automatic mocking of optional dependencies
3. Common test fixtures
"""
import os
import pytest
import sys
import tempfile
from unittest.mock import MagicMock
from typing import Dict, Any, List

# Register custom markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "performance: mark tests that check performance characteristics"
    )
    config.addinivalue_line(
        "markers", "optional_deps: mark tests that require optional dependencies"
    )
    config.addinivalue_line(
        "markers", "requires_internet: mark tests that require internet access"
    )

# List of optional modules that will be mocked if not available
# These are marked as optional in requirements-test.txt
OPTIONAL_MODULES = [
    'pysam',
    'pybigwig',
    'scanpy',
    'h5py',
    'anndata',
]

# List of core modules that should be available
# These are required in requirements-test.txt
CORE_MODULES = [
    'numpy',
    'pandas',
    'boto3',
    'requests',
    'pytest',
]

@pytest.fixture(autouse=True)
def mock_optional_imports(monkeypatch):
    """Mock optional imports that might be missing so tests can run.
    
    This fixture will:
    1. Mock any optional modules that aren't installed
    2. Verify required core modules are available (but don't fail if one is missing)
    """
    # Create more sophisticated mocks for common optional modules
    mocks = {}
    
    # Mock optional modules if they're not available
    for module_name in OPTIONAL_MODULES:
        if module_name not in sys.modules:
            # Create a basic mock
            mock_module = MagicMock()
            
            # Customize mocks for specific modules
            if module_name == 'h5py':
                # Create a mock for the File class
                mock_file = MagicMock()
                mock_module.File = MagicMock(return_value=mock_file)
                mock_module.is_hdf5 = MagicMock(return_value=True)
            elif module_name == 'scanpy':
                # Add basic AnnData reading capability to scanpy mock
                mock_module.read_h5ad = MagicMock()
                mock_module.read_10x_h5 = MagicMock()
            
            # Store the mock
            mocks[module_name] = mock_module
            monkeypatch.setitem(sys.modules, module_name, mock_module)
    
    # Check core modules but don't raise errors to allow tests to run anyway
    for module_name in CORE_MODULES:
        if module_name not in sys.modules:
            print(f"Warning: Required module {module_name} is not installed")

@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def mock_boto3():
    """Create a mock for boto3 with common AWS service mocks."""
    mock_s3 = MagicMock()
    mock_s3_client = MagicMock()
    
    # Configure S3 client responses
    mock_s3_client.put_object_tagging.return_value = {
        'ResponseMetadata': {'HTTPStatusCode': 200}
    }
    mock_s3_client.get_object_tagging.return_value = {
        'TagSet': [{'Key': 'validated', 'Value': 'true'}]
    }
    
    # Set up client returns
    mock_s3.return_value = mock_s3_client
    
    # Create the main boto3 mock
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    
    return mock_boto3

@pytest.fixture
def sample_s3_uri():
    """Return a sample S3 URI for testing."""
    return "s3://test-bucket/path/to/file.fastq.gz"

@pytest.fixture
def sample_validation_result() -> Dict[str, Any]:
    """Return a sample validation result for testing."""
    return {
        "success": True,
        "file_path": "test.fastq",
        "identifier": "TEST001",
        "results": {
            "valid": True,
            "errors": {},
            "warnings": {},
            "stats": {
                "read_count": 1000,
                "file_size": 1024000,
                "md5sum": "abcdef1234567890",
                "sha256": "abcdef1234567890abcdef1234567890",
                "crc32c": "12345678",
            }
        }
    }

@pytest.fixture
def sample_failed_result() -> Dict[str, Any]:
    """Return a sample failed validation result for testing."""
    return {
        "success": False,
        "file_path": "test.fastq",
        "identifier": "TEST002",
        "error": "File validation failed"
    } 