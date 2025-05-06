# HDF5/H5AD File Validation

## Overview

HDF5 and H5AD file formats require random access for validation, which means they cannot be properly validated via streaming. This document describes the implementation for handling these file types in the checkfiles validation system.

## Problem

The original implementation tried to validate HDF5/H5AD files by streaming directly from S3, which failed when using `seek()` on non-seekable streams. This caused validation to fail with errors related to `seek` operations.

## Solution

We've implemented a special workflow for HDF5 and H5AD formats:

1. HDF5/H5AD files are detected by their file format in `validate_s3_file`.
2. Instead of streaming, these files are downloaded to the `/mnt/scratch/` directory.
3. Validation is performed on the downloaded file using random access.
4. The file is deleted after validation is complete.

## Implementation Details

### 1. Special Format Detection

In the `validate_s3_file` function, we check if the file format is 'hdf5' or 'h5ad':

```python
if file_format.lower() in ['hdf5', 'h5ad']:
    logger.info(f"File format {file_format} requires random access. Downloading file for validation.")
    return download_and_validate_random_access_file(...)
```

### 2. Download and Validate Process

We've added a new function `download_and_validate_random_access_file` that:
- Downloads the file to the scratch directory
- Calculates hash values
- Validates the downloaded file
- Cleans up after validation

### 3. Scratch Directory

The system uses the `/mnt/scratch/` directory (configurable via the `SCRATCH_DIR` environment variable), which is created during EC2 instance setup in the Lambda function. If this directory isn't available, it falls back to the system temp directory.

### 4. Helper Functions

We added a `download_s3_file_to_scratch` helper function to handle:
- Creating unique filenames
- Downloading files using AWS CLI
- Error handling and reporting

### 5. Validator Improvements

Both `Hdf5Validator` and `H5adValidator` were updated to:
- Use the scratch directory for temporary files
- Better handle non-seekable streams
- Include clear documentation about random access requirements

## Testing

A comprehensive test suite was added in `tests/test_hdf5_validation.py` to verify:
- Download functionality
- Error handling
- Validation workflow
- Proper cleanup

## Usage

No changes are required from the user's perspective. The system automatically detects HDF5/H5AD files and applies the appropriate validation strategy.

## Logging

Enhanced logging was added to provide visibility into the download and validation process:
- Download start and completion
- File paths and cleanup
- Clear error messages for any failures

## Future Improvements

Potential improvements include:
- Implementing parallel hash calculation and validation to improve performance
- Adding validation for additional HDF5-based formats
- Optimizing disk usage for very large files 