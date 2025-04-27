# File Validators

This directory contains validators for various file formats used in genomic data processing.

## Validators

- **FastqValidator**: Validates FASTQ format files (DNA/RNA sequence reads)
- **BamValidator**: Validates BAM (Binary Alignment Map) files using samtools
- **CramValidator**: Validates CRAM (Compressed Reference-oriented Alignment Map) files using samtools

## External Dependencies

Some validators require external tools:

- **samtools**: Required for BAM and CRAM validation
  - Installed in Docker container
  - Installed on AMI via packer script
  - Installation instructions: [Samtools Documentation](http://www.htslib.org/download/)

## Usage

Each validator follows a common interface:

```python
from src.validators.bam import BamValidator

# Initialize validator
validator = BamValidator()

# Validate a file
result = validator.validate_file("path/to/file.bam")
if result["valid"]:
    print("File is valid!")
else:
    print("Validation errors:", result["errors"])

# You can also validate from a stream
from io import BytesIO
with open("path/to/file.bam", "rb") as f:
    content = f.read()
stream = BytesIO(content)
result = validator.validate_stream(stream)
```

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