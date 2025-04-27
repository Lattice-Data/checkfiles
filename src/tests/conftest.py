"""
Test configuration for pytest.
"""
import pytest

# Register custom markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "performance: mark tests that check performance characteristics"
    ) 