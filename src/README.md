# Checkfiles Source Code

## Streaming Validation Implementation

The validation system in checkfiles has been optimized for true streaming operation, particularly for large S3 files. This ensures efficient processing without storing large files on disk.

### Key Improvements

1. **Pure Streaming S3 Validation**
   - Files are validated directly from the S3 stream without creating temporary files
   - Prevents "No space left on device" errors when processing large files
   - Significantly reduces memory usage and eliminates disk I/O bottlenecks

2. **Single-Pass FASTQ Validation**
   - The FASTQ validator now processes files in a single pass rather than reading twice
   - Format validation and statistics collection happen simultaneously
   - No longer buffers large portions of the file in memory

3. **Pipe-Based BAM/CRAM Validation**
   - BAM and CRAM validators now pipe data directly to `samtools quickcheck`
   - No temporary files are created during validation
   - Memory usage remains constant regardless of file size

### Implementation Details

#### S3 File Processing
- Uses AWS CLI with streaming output piped directly to validators
- Progress tracking counts bytes processed without storing them
- Decompression of gzipped files happens on-the-fly using pipes

#### FASTQ Validation
- Processes 4-line blocks one at a time through a single stream iteration
- Validates format and collects statistics in the same pass
- Maintains error context with line numbers for accurate reporting

#### BAM/CRAM Validation
- Pipes data directly to samtools using subprocess stdin
- Processes files in chunks to maintain constant memory usage
- Reports total bytes processed for statistics

### Memory and Disk Usage

The improved implementation has the following characteristics:
- Memory usage remains nearly constant regardless of file size
- No disk usage for temporary storage of file content
- Processing time scales linearly with file size

These improvements ensure checkfiles can validate files of any size within reasonable memory constraints. 