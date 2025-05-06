## Validators Overview

This module provides file format validation for various scientific data formats:

- **FASTQ**: Validates FASTQ format files, including sequence quality, read names, and file structure.
- **HDF5**: Validates HDF5 format files, including structure and attributes.
- **H5AD**: Validates AnnData (H5AD) format files for single-cell genomics data.

## General Design

Each validator implements a consistent interface:

- `validate_file(file_path)`: Validates a file on disk
- `validate_stream(input_stream, is_gzipped)`: Validates a file stream (for S3 streaming)

### Validation Results

All validators return a standardized result dictionary:

```python
{
    "valid": bool,              # Whether the file passed validation
    "errors": {                 # Dictionary of errors encountered
        "error_type": "error message"
    },
    "warnings": {               # Dictionary of warnings (non-critical issues)
        "warning_type": "warning message"
    },
    "stats": {                  # Statistics about the file
        "file_size": int,       # Size in bytes
        "read_count": int,      # Number of reads (for sequence data)
        "read_length": int,     # Average read length (for sequence data)
        # Other format-specific stats
    }
}
```

## Validator Types

### FASTQ Validator

The FASTQ validator performs several checks:

1. File format validation (correct FASTQ structure)
2. Read name consistency
3. Quality score validation
4. Base composition analysis
5. Read length statistics

### HDF5 Validator

The HDF5 validator checks:

1. File format validity
2. Structure compliance
3. Required attributes

### H5AD Validator

The H5AD (AnnData) validator extends the HDF5 validator with specific checks for:

1. AnnData format compliance
2. Cell and gene metadata presence
3. Matrix data integrity

## Implementation Details

- **FASTQ**: Uses custom parsing with validation rules
- **HDF5/H5AD**: Uses h5py for validation

## Dependencies

- **h5py**: Required for HDF5 and H5AD validation

## Core Features

1. **Streaming Validation**:
   - All validators support stream-based validation
   - No temporary files are created during validation
   - Efficient for both local and S3 files

2. **Hash Calculation**:
   - Single-pass hash value calculation (MD5, SHA-256, CRC32C)
   - Content hashes for compressed files
   - Consistent hash reporting format

3. **Format Validation**:
   - Structure and format verification
   - Custom validation logic for each file type
   - Detailed error reporting

## Base Implementation

The `BaseValidator` class in `base.py` provides common functionality:

- `validate_file`: Process local files 
- `validate_stream`: Process streams (from memory, S3, etc.)
- `create_hash_calculating_stream`: Create a stream wrapper that calculates hashes
- `get_hash_values`: Get hash values from a stream
- `format_validation_result`: Format validation results consistently

## Stream-Based Architecture

```
┌────────────────┐
│   Input File   │
└───────┬────────┘
        │
┌───────▼────────┐
│   Open Stream   │
└───────┬────────┘
        │
┌───────▼────────────────┐
│ HashCalculatingStream  │
└───────┬────────────────┘
        │
┌───────▼────────┐
│ Calculate Hash │
└───────┬────────┘
        │
┌───────▼────────┐
│Validate Content│
└───────┬────────┘
        │
┌───────▼────────┐
│  Return Result │
└────────────────┘
```

## Using Validators

```python
from src.validators.fastq import FastqValidator

# Create validator
validator = FastqValidator()

# Validate a local file
result = validator.validate_file("/path/to/file.fastq")

# Validate a stream
with open("/path/to/file.fastq", "rb") as f:
    result = validator.validate_stream(f)

# Check validation result
if result["valid"]:
    print("File is valid")
    print(f"MD5: {result['stats']['md5sum']}")
else:
    print("Validation errors:", result["errors"])
```

## Implementation Notes

- **FASTQ**: Pure Python implementation with header parsing and statistics
- **HDF5**: Uses h5py to validate format and gather statistics

## External Dependencies

Some validators require external tools:

- **h5py**: Required for HDF5 validation

## Adding New Validators

To add a new validator:

1. Create a new file named after the format (e.g., `vcf.py` for VCF files)
2. Implement at minimum the `validate_file` and `validate_stream` methods
3. Add tests in the `src/tests/validators` directory
4. Update this README to include the new validator

## Testing

Run the tests using pytest:

```bash
pytest src/tests/validators/
```

For integration tests that require external tools:

```bash
pytest src/tests/validators/test_*_integration.py
``` 