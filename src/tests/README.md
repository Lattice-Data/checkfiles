# Testing for Checkfiles

This directory contains tests for the checkfiles project, which is used to validate
various file formats like FASTQ and HDF5.

## Test Suite Overview

This directory contains tests for the Checkfiles project, which validates
various file formats like FASTQ and HDF5.

### Directory Structure

```
tests/
├── conftest.py                # Common pytest fixtures
├── data/                      # Test data files
│   ├── fastq/                 # FASTQ test files
│   │   ├── invalid/           # Invalid FASTQ files for negative tests
│   │   └── valid/             # Valid FASTQ files for positive tests
│   └── hdf5/                  # HDF5 test files
│       ├── invalid/           # Invalid HDF5 files
│       └── valid/             # Valid HDF5 files
├── core/                      # Tests for core functionality
│   ├── test_validation.py     # Tests for the validation framework
│   └── test_utils.py          # Tests for utility functions
├── validators/                # Tests for individual validators
│   ├── test_fastq.py          # Tests for FASTQ validator
│   ├── test_fastq_enhanced.py # Tests for enhanced FASTQ validation
│   ├── test_hdf5.py           # Tests for HDF5 validator
│   └── test_base.py           # Tests for validator base class
├── utils/                     # Tests for utility modules
│   ├── test_helpers.py        # Tests for helper functions
│   └── test_s3_utils.py       # Tests for S3 utilities
└── test_checkfiles.py         # Main integration tests
```

### Running Tests

To run the test suite:

```bash
# Run all tests
pytest

# Run specific tests with more output
pytest tests/validators/test_fastq.py -v

# Run tests matching a pattern
pytest -k "fastq"

# Run tests with coverage report
pytest --cov=src
```

### Test Data

The `data/` directory contains sample files for testing:

- **FASTQ**: Sample FASTQ files with various formats and errors
- **HDF5**: Sample HDF5 files with different structures

### Testing Approach

1. **Unit Tests**: Test individual components in isolation
   - Test validator functions with simple mock inputs
   - Test utility functions with specific inputs and expected outputs

2. **Integration Tests**: Test interactions between components
   - Test CLI with actual file inputs
   - Test validation pipeline end-to-end

3. **Mock Testing**: Use mocks for external dependencies
   - Mock S3 client responses
   - Mock subprocess calls for external tools

### Key Test Features

- Fixtures for common setup and teardown
- Parameterized tests for comprehensive test coverage
- Streaming validation tests without local file storage
- Memory usage verification for large files

### Continuous Integration

Tests run automatically on:
- Pull requests
- Merges to main branch
- Scheduled daily runs

## Test Approach

The tests are organized into different categories:

1. **Unit Tests**: These test individual components in isolation.
2. **Integration Tests**: These test how components work together.
3. **Validator Tests**: Specialized tests for each file format validator.

## Streaming Implementation

Recent improvements have been made to support stream-based validation instead of
temporary files. This enables:

- More efficient validation of large files
- S3 streaming without downloading entire files to disk
- Better memory management, especially for large files
- Consistent hash calculation in a single pass

### Key Implementation Details

- `HashCalculatingStream` wrapper calculates multiple hashes in a single pass
- Validators use memory buffers instead of temporary files
- BAM/CRAM validators pipe streams directly to samtools
- Clear separation between hash calculation and content validation

## Running Tests

To run the tests:

```bash
# Run all tests
python -m pytest

# Run specific test files
python -m pytest src/tests/validators/test_fastq_validator.py

# Run with coverage
python -m pytest --cov=src
```

## Adding New Tests

When adding new tests, follow these principles:

1. Use descriptive test names that explain what is being tested
2. Set up test fixtures in conftest.py when they'll be used by multiple tests
3. Prefer in-memory streams over file I/O for faster tests
4. Properly mock external dependencies
5. Clean up temporary files and resources

## GitHub Actions CI

Testing is automated using GitHub Actions for:
- Running tests on multiple Python versions
- Linting and code quality checks
- Coverage reporting

CI workflows are defined in `.github/workflows/`. 