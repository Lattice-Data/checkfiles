# Checkfiles Source Code Documentation

This directory contains the main source code for the Checkfiles project, a system for validating various file formats used in scientific research.

## Directory Structure

```
src/
├── cli/                # Command-line interface components
│   └── parser.py       # Argument parsing for CLI
├── core/               # Core validation framework
│   └── validation.py   # Base validation functionality
├── models/             # Data models
│   └── validation_record.py  # Validation result structure
├── path_translator/    # Path translation utilities
├── tracking/           # Progress tracking components
│   └── progress.py     # Progress visualization
├── utils/              # Utility functions
│   ├── helpers.py      # Common helper functions
│   └── s3_utils.py     # S3 interaction utilities
├── validators/         # File format validators
│   ├── fastq_validator.py  # FASTQ file validator
│   ├── h5_validator.py     # HDF5 file validator
│   └── h5ad_validator.py   # H5AD file validator
└── worker/             # Worker process components
    └── patch_worker.py # Background worker functionality
```

## Core Components

### 1. Validation Framework (`core/validation.py`)

The validation framework provides:

- Base validator classes for all file formats
- Standard validation result structure
- Common validation utilities
- Memory-efficient streaming validation

```python
# Example of validation record creation
from src.core.validation import create_validation_record

record = create_validation_record(
    validation_result, 
    file_path, 
    file_uuid,
    file_etag
)
```

### 2. File Format Validators

Each supported file format has a dedicated validator:

#### FASTQ Validator (`validators/fastq_validator.py`)

Validates FASTQ files, including:
- Header format checking
- Quality score validation
- Read name consistency
- Base composition statistics
- Supports both compressed (.gz) and uncompressed files

#### HDF5 Validator (`validators/h5_validator.py`)

Validates HDF5 files, including:
- File structure validation
- Attribute verification
- Dataset integrity checking

#### H5AD Validator (`validators/h5ad_validator.py`)

Validates AnnData single-cell genomics data, including:
- AnnData structure compliance
- Observation and variable verification
- Genome annotation checking

### 3. Progress Tracking (`tracking/progress.py`)

The progress tracking system provides:

- Real-time progress reporting
- Estimated time remaining
- Success/failure tracking
- Terminal-based visual feedback

```python
# Example of progress tracker usage
from src.tracking.progress import SimpleActivityTracker

tracker = SimpleActivityTracker(total_files=10)
tracker.start_file("file.fastq.gz")
# ... validation code ...
tracker.complete_file("file.fastq.gz", success=True, results=results)
```

### 4. S3 Integration (`utils/s3_utils.py`)

S3 integration features include:

- Direct validation from S3 without full download
- Streaming validation for large files
- S3 tagging for tracking validation status
- Automatic credential handling

```python
# Example of S3 tagging
from src.utils.s3_utils import set_s3_tags

set_s3_tags(
    s3_uri="s3://bucket/file.fastq.gz",
    tags={"validated": "true", "valid": "true"}
)
```

## Usage Examples

### Validating a Local File

```python
from src.core.validation import initialize_validator

# Initialize validator for a FASTQ file
validator = initialize_validator("fastq", "/path/to/file.fastq.gz")

# Validate the file
result = validator.validate()

# Check result
if result.get("valid", False):
    print("File is valid!")
else:
    print(f"File is invalid: {result.get('errors', {})}")
```

### Validating an S3 File

```python
from src.checkfiles import validate_s3_file

# Validate an S3 file
result = validate_s3_file(
    s3_path="s3://bucket/file.fastq.gz",
    file_format="fastq",
    debug=True
)

# Check result
if result.validation_success:
    print("Validation successful!")
    print(f"File valid: {result.info.get('valid', False)}")
else:
    print(f"Validation failed: {result.errors}")
```

## Adding a New Validator

To add support for a new file format:

1. Create a new validator class in `src/validators/`
2. Implement the required interface methods:
   - `__init__(self, file_path)`
   - `validate(self)`
   - `get_file_info(self)`
3. Register the validator in `src/core/validation.py`

Example template for a new validator:

```python
class NewFormatValidator:
    def __init__(self, file_path):
        self.file_path = file_path
        # Initialize any required resources
        
    def validate(self):
        """Validate the file and return results."""
        # Implement validation logic
        results = {
            "valid": True,  # Set to False if validation fails
            "errors": {},   # Include error details if any
            # Add format-specific stats
        }
        return results
        
    def get_file_info(self):
        """Return file metadata and statistics."""
        # Implement file info gathering
        return {
            "file_size": 1234,
            "md5sum": "abc123...",
            # Add format-specific metadata
        }
```

## Performance Optimization

The codebase includes several optimizations for processing large files:

1. **Streaming Processing**: Files are processed in chunks to minimize memory usage
2. **Parallel Execution**: Multi-process validation for handling multiple files
3. **Early Termination**: Validation stops as soon as errors are detected
4. **Efficient S3 Access**: Uses S3 GetObject with Range requests for partial file access

## Testing

Each validator and component has dedicated tests in the `tests/` directory:

```bash
# Run all tests
python -m pytest

# Run tests for a specific validator
python -m pytest tests/validators/test_fastq_validator.py

# Run tests with coverage
python -m pytest --cov=src tests/
```

## Future Development

Planned improvements include:

1. **Additional File Formats**:
   - BAM/CRAM genomic alignment files
   - VCF variant call files
   - GFF/GTF genome annotation files

2. **Enhanced Validation**:
   - More detailed sequence quality metrics
   - Cross-file validation for related files
   - Machine learning-based anomaly detection

3. **Performance Enhancements**:
   - GPU acceleration for sequence analysis
   - Improved streaming for very large files
   - Distributed processing across multiple nodes

## Contributing

Please see the main [CONTRIBUTING.md](../CONTRIBUTING.md) file for guidelines on contributing to the project. 