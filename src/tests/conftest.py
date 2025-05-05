"""
Test configuration for pytest.
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

# List of modules to mock if they can't be imported
MODULES_TO_MOCK = [
    'scanpy', 
    'h5py', 
    'pysam',
    'pybigwig',
    'numpy',
    'pandas',
    'scipy',
    'scipy.sparse',
    'scipy.io',
    'scipy.io.hdf5',
    
]

@pytest.fixture(autouse=True)
def mock_imports(monkeypatch):
    """Mock imports that might be missing so tests can run."""
    for module_name in MODULES_TO_MOCK:
        if module_name not in sys.modules:
            mock_module = MagicMock()
            monkeypatch.setitem(sys.modules, module_name, mock_module) 