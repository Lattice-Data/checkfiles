# File Validators

This directory contains validators for different file formats used in scientific and bioinformatics applications.

## Available Validators

- **BAM**: Validates Binary Alignment/Map files using samtools.
- **CRAM**: Validates CRAM format files using samtools.
- **FASTQ**: Validates FASTQ sequence files with quality scores.
- **HDF5**: Validates HDF5 hierarchical data format files.

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

- **BAM/CRAM**: Use samtools for validation via subprocess
- **FASTQ**: Pure Python implementation with header parsing and statistics
- **HDF5**: Uses h5py to validate format and gather statistics

## External Dependencies

Some validators require external tools:

- **samtools**: Required for BAM and CRAM validation
  - Installed in Docker container
  - Installed on AMI via packer script
  - Installation instructions: [Samtools Documentation](http://www.htslib.org/download/)

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