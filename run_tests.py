"""
Test runner for the checkfiles package.
"""
import pytest
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_tests():
    """Run all tests in the src/tests directory using pytest."""
    args = ["-xvs", "src/tests"]
    return pytest.main(args)

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)