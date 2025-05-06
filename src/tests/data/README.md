# Test Data

This directory contains test data for validating various file formats.

## Directory Structure

- `fastq/` - FASTQ test files
  - `valid/` - Valid FASTQ files that should pass validation
  - `invalid/` - Invalid FASTQ files that should fail validation

## Test Files

### FASTQ Files

- Valid:
  - `small.fastq` - A small valid FASTQ file
  - `small.fastq.gz` - A small valid gzipped FASTQ file

- Invalid:
  - `corrupted_header.fastq` - A FASTQ file with a corrupted header
  - `truncated.fastq` - A truncated FASTQ file
  - `invalid_quality.fastq` - A FASTQ file with invalid quality scores

## Generating Test Data

Run the `download_test_data.sh` script to download and generate test files:

```bash
./download_test_data.sh
```

This script will download sample files from public repositories and create invalid test cases. 