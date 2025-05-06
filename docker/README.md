# Docker Guide for Checkfiles

This guide explains how to run the Checkfiles validation tool using Docker, which is the easiest way to get started without complex setup.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Step-by-Step Tutorial](#step-by-step-tutorial)
- [Validation Examples](#validation-examples)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

## Prerequisites

- [Docker Engine](https://docs.docker.com/get-docker/) installed on your computer
- [Docker Compose V2](https://docs.docker.com/compose/install/) (version 2.10.0+)
- AWS credentials (only required if validating S3 files)

## Quick Start

1. Create a test data directory and add your files:
```bash
# From project root
mkdir -p test_data
# Add your .fastq.gz files to test_data/
```

2. Build and run:
```bash
# From project root
docker compose -f docker/docker-compose.yml up
```

3. In a new terminal window, run the validation:
```bash
# Validate a local file
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/test_data/your_file.fastq.gz
```

## Step-by-Step Tutorial

### 1. Installing Docker

If you don't have Docker installed:

- **Windows/Mac**: Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Linux**: Follow the [installation guide](https://docs.docker.com/engine/install/) for your distribution

After installation, verify Docker is running:
```bash
docker --version
```

### 2. Setting Up Test Files

Create a directory for your test files:
```bash
mkdir -p test_data
```

You can now place any files you want to validate in this directory. For example, if you have FASTQ files (`.fastq` or `.fastq.gz`), copy them to the `test_data` directory.

### 3. Starting the Docker Container

From the project root directory, run:
```bash
docker compose -f docker/docker-compose.yml up
```

This command:
- Builds the Docker container (first time only)
- Starts the container
- Shows the help message

The terminal will remain open showing logs. Leave this running and open a new terminal window for the next steps.

### 4. Running Validation

In a new terminal window, navigate to the project root and run:

```bash
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/test_data/your_file.fastq.gz
```

Replace `your_file.fastq.gz` with the actual filename in your test_data directory.

### 5. Understanding the Results

After running validation, you'll see output like:

```
=== Validation Summary ===
Total files: 1
Successfully processed: 1
Valid files: 1
Invalid files: 0
Failed to process: 0

=== Detailed Results ===
/app/test_data/your_file.fastq.gz: Valid
  File size: 358420 bytes
  Uncompressed size: 1234567 bytes
  MD5: abc123...
```

The validation results are also saved to log files in the `logs` directory:
```bash
# View progress log
cat logs/validation_progress.log

# View debug log
cat logs/checkfiles_debug.log
```

## Validation Examples

### Local File Validation

```bash
# Single file
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/test_data/file1.fastq.gz

# Multiple files (comma-separated, NO spaces)
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l "/app/test_data/file1.fastq.gz,/app/test_data/file2.fastq.gz"

# With debug output
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/test_data/file1.fastq.gz -d
```

### S3 File Validation

First, set up your AWS credentials in your terminal:
```bash
# Replace with your actual AWS credentials
export AWS_ACCESS_KEY_ID=your-key-id
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-west-2
```

Then run validation:
```bash
# Single S3 file
docker compose -f docker/docker-compose.yml run checkfiles \
    -f fastq \
    -s3 s3://your-bucket/path/to/file.fastq.gz
```

### Host Path Translation

Docker automatically translates paths between your host computer and the container:

```bash
# Using host path (works on Mac/Linux)
docker compose -f docker/docker-compose.yml run checkfiles \
    -f fastq \
    -l /Users/yourusername/Documents/file.fastq.gz
```

This works because the container automatically detects host paths and maps them correctly.

## Environment Variables

| Variable | Description | Default | Required for S3 |
|----------|-------------|---------|-----------------|
| AWS_ACCESS_KEY_ID | AWS access key | None | Yes |
| AWS_SECRET_ACCESS_KEY | AWS secret key | None | Yes |
| AWS_DEFAULT_REGION | AWS region | us-west-2 | Yes |
| LOG_LEVEL | Python logging level | INFO | No |
| PYTHONUNBUFFERED | Enables unbuffered Python output | 1 | No |

## Troubleshooting

### Permission Issues

If you see "Permission denied" errors for logs:
```bash
sudo chown -R $(id -u):$(id -g) logs/
```

### Container Won't Start

1. Check if Docker is running:
   ```bash
   docker info
   ```

2. Check for port conflicts:
   ```bash
   docker ps
   ```

3. Verify Docker Compose is installed:
   ```bash
   docker compose version
   ```

### AWS Credentials Not Working

1. Check you've exported credentials correctly:
   ```bash
   echo $AWS_ACCESS_KEY_ID
   echo $AWS_SECRET_ACCESS_KEY
   ```

2. Verify region matches your bucket:
   ```bash
   echo $AWS_DEFAULT_REGION
   ```

3. Test AWS CLI access:
   ```bash
   aws s3 ls s3://your-bucket/
   ```

### File Not Found or Invalid Format

1. Verify the file exists in the test_data directory:
   ```bash
   ls -la test_data/
   ```

2. Check if the file format is supported (fastq, h5, h5ad):
   ```bash
   # For .fastq files:
   docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/test_data/file.fastq.gz

   # For .h5 files:
   docker compose -f docker/docker-compose.yml run checkfiles -f h5 -l /app/test_data/file.h5

   # For .h5ad files:
   docker compose -f docker/docker-compose.yml run checkfiles -f h5ad -l /app/test_data/file.h5ad
   ```

## Advanced Usage

### Interactive Shell

For debugging or advanced usage:
```bash
docker compose -f docker/docker-compose.yml run --entrypoint bash checkfiles
```

This gives you a shell inside the container where you can run commands directly.

### Viewing Container Logs

```bash
# View logs of the container
docker compose -f docker/docker-compose.yml logs
```

### Stopping the Container

```bash
# Stop containers but preserve data
docker compose -f docker/docker-compose.yml down

# Clean up everything including volumes
docker compose -f docker/docker-compose.yml down -v

# Remove everything including built images
docker compose -f docker/docker-compose.yml down -v --rmi all
```

### Available Command Arguments

For a complete list of available arguments:
```bash
docker compose -f docker/docker-compose.yml run checkfiles --help
```