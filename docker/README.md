# Docker Guide for Checkfiles

This directory contains Docker configuration for running the Checkfiles validation tool in a containerized environment.

## Prerequisites

- Docker Engine
- Docker Compose V2 (version 2.10.0+)
- AWS credentials (if using S3 functionality)

## Quick Start

First, create a test data directory and add your files:
```bash
# From project root
mkdir -p test_data
# Add your .fastq.gz files to test_data/
```

Then build and run:
```bash
# Build and run from project root
docker compose -f docker/docker-compose.yml up

# Or cd into docker directory
cd docker
docker compose up
```

By default, this will show the help message. To validate files, see the Usage Examples below.

## Features

- Single container with all dependencies pre-installed
- Python 3.11 environment with type hints and proper documentation
- Support for both local file and S3 file validation
- No need to install dependencies locally
- Health checks to ensure service availability
- Volume mapping for easy file access

## Environment Variables

| Variable | Description | Default | Required for S3 |
|----------|-------------|---------|-----------------|
| AWS_ACCESS_KEY_ID | AWS access key | None | Yes |
| AWS_SECRET_ACCESS_KEY | AWS secret key | None | Yes |
| AWS_DEFAULT_REGION | AWS region | us-west-2 | Yes |
| LOG_LEVEL | Python logging level | INFO | No |
| PYTHONUNBUFFERED | Enables unbuffered Python output | 1 | No |

## Recent Updates

### Path Handling Improvements
- Added ability to use both host file paths and container paths
- Files can now be specified with absolute paths from the host system
- Automatic path translation between host and container filesystems
- S3 URIs continue to work as before

### Validation Improvements
- Fixed validation for FASTQ files with mismatched IDs in header and quality lines
- Mismatched IDs are now correctly treated as errors instead of warnings
- Test service added to verify validation behavior

## Usage

### Building the Container

```bash
docker compose -f docker/docker-compose.yml build
```

### Running Validation on S3 Files

```bash
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -s3 s3://your-bucket/path/to/file.fastq.gz
```

### Running Validation on Local Files

```bash
# Using container path
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/src/tests/data/fastq/invalid/mismatched_ids.fastq

# Using host path (will be automatically translated)
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /Users/yourusername/path/to/file.fastq
```

### Testing FASTQ Validation with Mismatched IDs

```bash
docker compose -f docker/docker-compose.yml run test-mismatched-ids
```

This will run the validator on a test file with mismatched IDs in the header and quality lines, which should be reported as invalid.

## File Format Validation

The container supports validation of the following file formats:

- FASTQ (with or without gzip compression)
- BAM
- CRAM

Each format has specific validation criteria. See the individual validator documentation for details.

## Usage Examples

### Run validation on local files
```bash
# Basic usage with local file
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/test_data/test.fastq.gz

# Multiple local files (comma-separated)
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l "/app/test_data/file1.fastq.gz,/app/test_data/file2.fastq.gz"
```

### Run validation on S3 files

1. First, set up your AWS credentials in your terminal:
```bash
# Replace these with your actual AWS credentials
export AWS_ACCESS_KEY_ID=your-key-id
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-west-2
```

2. Then run the validation with your S3 file path:
```bash
# Single S3 file
docker compose -f docker/docker-compose.yml run checkfiles \
    -f fastq \
    -s3 s3://your-bucket/path/to/file.fastq.gz

# Multiple S3 files (comma-separated, no spaces)
docker compose -f docker/docker-compose.yml run checkfiles \
    -f fastq \
    -s3 s3://bucket/file1.fastq.gz,s3://bucket/file2.fastq.gz

# With debug output
docker compose -f docker/docker-compose.yml run checkfiles \
    -f fastq \
    -s3 s3://your-bucket/path/to/file.fastq.gz \
    -d
```

Note: Make sure your AWS credentials have permission to access the specified S3 bucket and objects.

### Run interactively for debugging
```bash
docker compose -f docker/docker-compose.yml run --entrypoint bash checkfiles
```

## Development

The Docker setup mounts your local `src` and `test_data` directories:
- `src`: Contains the Python source code (mounted read-only)
- `test_data`: Contains test files for validation (mounted read-only)
- `logs`: Directory for log output (mounted read-write)

To apply changes to dependencies:
```bash
docker compose -f docker/docker-compose.yml build --no-cache
```

### Testing

When writing tests for the application, ensure:
- Unit tests cover at least 80% of the code
- All tests follow the Google Python Style Guide
- Tests are properly documented with docstrings
- Test fixtures are reusable and well-named

## Container Management

### View running containers
```bash
docker ps
```

### Inspect container health
```bash
docker inspect --format='{{json .State.Health}}' $(docker ps -q --filter name=checkfiles)
```

### Stop and remove containers
```bash
# Stop containers but preserve data
docker compose -f docker/docker-compose.yml down

# Clean up everything including volumes
docker compose -f docker/docker-compose.yml down -v

# Remove everything including built images
docker compose -f docker/docker-compose.yml down -v --rmi all
```

## Troubleshooting

### Permission issues
If you encounter permission problems with mounted volumes:
```bash
sudo chown -R $(id -u):$(id -g) .
```

### Common issues

1. **Missing test_data directory**
   - Create the directory: `mkdir -p test_data`
   - Add your test files to it

2. **AWS credentials not working**
   - Verify credentials are exported in your environment
   - Check AWS region is correct
   - Ensure S3 bucket/object permissions are set correctly

3. **Container fails to start**
   - Check if ports are already in use
   - Verify Docker service is running
   - Check system resources (memory/disk space)
   - Review logs: `docker compose -f docker/docker-compose.yml logs`

4. **Health check failures**
   - Check if Python modules are properly installed
   - Verify the application code is properly mounted
   - Inspect logs for initialization errors

## Script Arguments

The checkfiles script supports the following arguments:

```bash
-f, --file-format    Specify the file format (e.g., fastq)
-l, --local-file     Specify local file(s) to validate (comma-separated)
-s3, --s3-file       Specify S3 file(s) to validate (comma-separated)
-d, --debug          Enable debug output
-t, --threads        Number of threads for parallel processing
-q, --quiet          Suppress progress indicators
--log-file          Path to log file
```

For full usage instructions, run:
```bash
docker compose -f docker/docker-compose.yml run checkfiles --help
```