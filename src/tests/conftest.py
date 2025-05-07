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
# These may be conditionally used in the codebase but are not required
OPTIONAL_MODULES = [
    'pysam',
    'pybigwig',
]

# List of core modules that should be available
# These are defined in pyproject.toml under [project.dependencies]
CORE_MODULES = [
    'scanpy', 
    'h5py', 
    'numpy',
    'pandas',
    'scipy',
    'boto3',
    'crcmod',
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
            raise ImportError(f"Required module {module_name} is not installed. Run: pip install '.[test]'") 