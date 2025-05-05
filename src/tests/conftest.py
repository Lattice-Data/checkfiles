"""
Test configuration for pytest.

This module provides:
1. Custom pytest markers
2. Automatic mocking of optional dependencies
3. Common test fixtures
"""
import pytest
import sys
from unittest.mock import MagicMock

# Register custom markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "performance: mark tests that check performance characteristics"
    )

# List of optional modules that will be mocked if not available
# These are marked as optional in requirements-test.txt
OPTIONAL_MODULES = [
    'pysam',
    'pybigwig',
]

# List of core modules that should be available
# These are required in requirements-test.txt
CORE_MODULES = [
    'scanpy', 
    'h5py', 
    'numpy',
    'pandas',
    'scipy',
    'scipy.sparse',
    'scipy.io',
    'scipy.io.hdf5',
]

@pytest.fixture(autouse=True)
def mock_optional_imports(monkeypatch):
    """Mock optional imports that might be missing so tests can run.
    
    This fixture will:
    1. Mock any optional modules that aren't installed
    2. Raise an error if any core modules are missing
    """
    # Mock optional modules if they're not available
    for module_name in OPTIONAL_MODULES:
        if module_name not in sys.modules:
            mock_module = MagicMock()
            monkeypatch.setitem(sys.modules, module_name, mock_module)
    
    # Verify core modules are available
    for module_name in CORE_MODULES:
        if module_name not in sys.modules:
            raise ImportError(f"Required module {module_name} is not installed") 