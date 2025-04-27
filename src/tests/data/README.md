# Test Data

This directory contains test data for validating various file formats.

## Directory Structure

- `bam/` - BAM (Binary Alignment Map) test files
  - `valid/` - Valid BAM files that should pass validation
  - `invalid/` - Invalid BAM files that should fail validation
- `cram/` - CRAM test files
  - `valid/` - Valid CRAM files that should pass validation
  - `invalid/` - Invalid CRAM files that should fail validation
- `fastq/` - FASTQ test files
  - `valid/` - Valid FASTQ files that should pass validation
  - `invalid/` - Invalid FASTQ files that should fail validation

## Test Files

### BAM Files

- Valid:
  - `small.bam` - A small valid BAM file from ENA

- Invalid:
  - `corrupted_header.bam` - A BAM file with a corrupted header
  - `truncated.bam` - A truncated BAM file

### CRAM Files

- Valid:
  - `small.cram` - A small valid CRAM file from ENA

- Invalid:
  - `corrupted_header.cram` - A CRAM file with a corrupted header
  - `truncated.cram` - A truncated CRAM file

## Generating Test Data

Run the `download_test_data.sh` script to download and generate test files:

```bash
./download_test_data.sh
```

This script will download sample files from public repositories and create invalid test cases. 