# Checkfiles Source Code

## Checkfiles Project Structure

This directory contains the main source code for the Checkfiles project.

### Key Components

1. **Core Validation Framework**
   - Base validator classes and common utilities
   - Abstract interfaces for file and stream validation
   - Standardized validation result formats

2. **Specialized Validators**
   - FASTQ validators with enhanced quality checking
   - HDF5/H5AD validation with structure verification
   - Extensible framework for adding new validators

3. **Stream Processing**
   - Memory-efficient validation of large files
   - S3 integration for direct validation without local storage
   - Streaming validation for all supported formats

4. **CLI & API**
   - Command-line interface with multiple modes
   - Backend API for integration with data portals
   - Configuration management and logging

### Recent Improvements

1. **Enhanced FASTQ Validation**
   - Improved read name validation
   - Quality score distribution analysis
   - Base composition statistics

2. **Optimized Memory Usage**
   - Streaming validation for all formats
   - Progress tracking for long-running validations
   - Reduced peak memory usage for large files

3. **Parallel Processing**
   - Multi-process validation support
   - Configurable thread counts
   - Automatic scaling based on available resources

### File Formats Supported

- **FASTQ**: Sequence reads with quality scores
- **HDF5**: Hierarchical data format
- **H5AD**: AnnData single-cell genomics data

### Development

1. **Testing**
   - Unit tests for all validators
   - Integration tests with real file examples
   - Performance benchmarking

2. **Documentation**
   - Validator-specific README files
   - API documentation
   - Usage examples

3. **Future Plans**
   - Additional file format support
   - Enhanced reporting
   - Cloud function deployment 