[![Coverage Status](https://coveralls.io/repos/github/Lattice-Data/checkfiles/badge.svg?branch=main)](https://coveralls.io/github/Lattice-Data/checkfiles?branch=main)

# Checkfiles

A scalable system for processing and validating files. It supports both local validation on your computer and remote validation using cloud services. This project provides tools and automation for validation workflows.

## Table of Contents
- [Overview](#overview)
- [Getting Started](#getting-started)
- [Command Reference](#command-reference)
- [Supported File Formats](#supported-file-formats)
- [Monitoring and Logs](#monitoring-and-logs)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Overview

Checkfiles is a versatile file validation system that:
- Supports validation both on your local computer and through cloud-based services
- Performs format-specific validation of files (FASTQ, H5, H5AD formats supported)
- Tracks progress of the validation process
- Provides file format specific summary statistics
- Automatically scales up cloud-based validation according to the quantity of files

## Getting Started

### Clone the Repository

Start by cloning the repository to your local machine:

```bash
git clone https://github.com/Lattice-Data/checkfiles.git
cd checkfiles
```

### Choose Your Validation Method

Checkfiles supports two primary validation methods:

1. **Local validation using Docker** - For validating files on your own computer (including both local files and files stored in S3 buckets)
   * Follow the instructions in the [Docker README](docker/README.md) for setup and execution

2. **Cloud-based validation** - For validating files submitted to production portal ("https://www.lattice-data.org/") or demo data portal using query-based file selection
   * Follow the instructions in the [CDK README](cdk/README.md) for setup and execution

## Command Reference

### Common Parameters
The following parameters can be used with both local and cloud-based execution:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-d`, `--debug` | Enable debug output | `-d` |
| `-t`, `--threads` | Number of processing threads | `-t 4` |

### Local Execution Parameters (Docker)
The following parameters are used with local Docker-based execution:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-f`, `--file-format` | File format to validate | `-f fastq` |
| `-l`, `--local-file` | Local file path(s) | `-l /path/to/file.fastq.gz` |
| `-s3`, `--s3-file` | S3 file URI(s) | `-s3 s3://bucket/file.fastq.gz` |

### Cloud-Based Execution Parameters
The following parameters are only used for cloud-based execution:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--backend-uri` | URI of backend service | `--backend-uri https://api.example.com` |
| `--query` | Query string for backend | `--query "type=file&format=fastq"` |
| `--update` | Update backend with results | `--update` |

### Thread Count Calculation

Think of threads like workers that process your files. When you use the `-t` parameter, here's how the program decides how many workers to use:

- By default, the program uses as many workers as your computer has (but never more than the number of files you're checking)
- If you ask for fewer workers with `-t 2`, the program will only use that many
- The program will always use at least 1 worker
- **The more workers you provide, the more files can be validated in parallel, which significantly speeds up processing when handling multiple files**

Example: If your computer has 8 cores (workers available), but you only have 5 files to check, the program will use 5 workers. If you specify `-t 3`, it will only use 3 workers.

## Supported File Formats

Checkfiles currently supports the following file formats:

- **FASTQ**: compressed sequencing reads (`.fastq.gz`)
- **H5**: Single-cell hierarchical data matrix (`.h5`)
- **H5AD**: AnnData annotated single-cell data matrix (`.h5ad`)

Each format has specific validators that check for:
- Format compliance
- Data integrity
- Content validation
- Metadata correctness
- Size and compression verification

## Architecture

For those interested in the technical implementation, the system consists of several components:

### 1. Cloud Functions
- Monitor for pending files
- Manage processing instances
- Execute file validation
- Provide status information
- Track processing metrics

### 2. Infrastructure
- Cloud-based infrastructure as code
- Automated deployment pipelines
- Resource management and scaling

### 3. Machine Image Builder
- Custom machine image creation for processing instances
- Environment configuration
- Dependency management

### 4. Source Code
- Core processing logic
- Utility functions
- Test suites

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please:
1. Check the documentation
2. Search existing issues
3. Create a new issue if needed