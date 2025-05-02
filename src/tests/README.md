# Testing for Checkfiles

This directory contains tests for the checkfiles project, which is used to validate
various file formats like FASTQ, BAM, CRAM, and HDF5.

## Directory Structure

```
src/tests/
├── validators/               # Tests for specific file format validators
│   ├── data/                 # Test data files for validation tests
│   ├── test_bam.py           # Tests for BAM validator
│   ├── test_bam_integration.py  # Integration tests for BAM validator
│   ├── test_cram.py          # Tests for CRAM validator
│   ├── test_cram_integration.py # Integration tests for CRAM validator
│   ├── test_fastq.py         # Tests for FASTQ validator
│   ├── test_fastq_enhanced.py # Extended tests for FASTQ validator
│   ├── test_fastq_readnames.py # Tests for FASTQ read name parsing
│   ├── test_fastq_validator.py # Tests for the FASTQ validator class
│   └── test_hdf5.py          # Tests for HDF5 validator
├── test_checkfiles.py        # Main tests for the checkfiles module
├── conftest.py               # Pytest configuration and fixtures
└── README.md                 # This file
```

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