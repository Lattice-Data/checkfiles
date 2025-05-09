# Docker Guide for Checkfiles Validation Service

This guide helps you run the Checkfiles validation tool using Docker. The tool validates various file formats.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Supported File Types](#supported-file-types)
- [Step-by-Step Tutorial](#step-by-step-tutorial)
- [Example Output](#example-output)
- [Destroying Containers](#destroying-containers)

## Prerequisites

### 1. Install Docker Engine on Mac

1. Download Docker Desktop for Mac from [Docker's official website](https://www.docker.com/products/docker-desktop/)
2. Double-click the downloaded `.dmg` file and drag Docker to your Applications folder
3. Open Docker Desktop from your Applications folder
4. Wait for Docker to start (the whale icon in the menu bar will stop animating when ready)
5. Verify installation by opening Terminal and typing:
   ```bash
   docker --version
   ```
   You should see output showing the Docker version, for example:
   ```
   Docker version 28.0.4, build b8034c0
   ```
6. Configure Docker Desktop with more memory:
   - Click the Docker icon (whale) in the Mac menu bar
   - Select "Settings" (gear icon)
   - Go to "Resources" in the left sidebar
   - Increase the "Memory" allocation to at least 8GB (8192MB)
   - Click "Apply & Restart" to save changes
   
   This step is crucial for running Checkfiles as it requires sufficient memory for processing large files.

7. Important note for Mac users: When running Docker for the first time, you may see permission prompts asking to allow Docker to access your filesystem, network, etc. Be sure to approve these requests when they appear, as Docker needs these permissions to function properly.

### 2. AWS Credentials Setup (Required for S3 access)

To validate files stored in Amazon S3, you need AWS credentials:

**Option 1: Environment Variables**
Set these in your terminal before running Docker commands:
```bash
export AWS_ACCESS_KEY_ID=your-access-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-access-key
export AWS_DEFAULT_REGION=us-west-1  # Change to your region if needed
```

**Option 2: AWS Credentials File**
Create or edit the file `~/.aws/credentials`:
```
[default]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
region = us-west-1
```

## Supported File Types

The Checkfiles validation service supports the following file formats:

### FASTQ Files
Command flag: `-f fastq`

**Validation checks:**
- File integrity
- FASTQ format compliance
- Read ID consistency
- Sequence quality scores

**Statistics calculated:**
- File size
- Read count
- Average read length
- Various hash functions such as md5sum, sha256, crc32

### H5 Files (HDF5)
Command flag: `-f h5`

**Validation checks:**
- File format integrity
- Dataset accessibility
- Attribute consistency

**Statistics calculated:**
- File size
- Number of datasets
- Dataset dimensions
- Memory usage
- MD5 checksum

### H5AD Files (AnnData)
Command flag: `-f h5ad`

**Validation checks:**
- File format integrity
- Data structure compliance
- Metadata consistency

**Statistics calculated:**
- File size
- Cell count
- Gene count
- Layer information
- MD5 checksum

## Step-by-Step Tutorial

This guide assumes you have already cloned the repository as described in the main [README.md](../README.md).

### Validating Local Files

1. Navigate to the checkfiles directory in your terminal:
   ```bash
   cd /path/to/checkfiles
   ```

2. Build the Docker container (first time only):
   ```bash
   docker compose -f docker/docker-compose.yml build
   ```
   Note: Ensure Docker Engine (Docker Desktop on Mac) is running before executing this command.

3. Run validation on a local file:
   ```bash
   docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /path/to/your_file.fastq.gz
   ```

   **Flag explanation:**
   - `-f fastq`: Specifies the file format. Only three formats are supported: fastq, h5, or h5ad
   - `-l /path/to/file`: Path to your local file(s)

   **Multiple files:** To validate multiple files at once, provide comma-separated paths (no spaces):
   ```bash
   docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l "/path/to/file1.fastq.gz,/path/to/file2.fastq.gz"
   ```

4. View the results:
   - Real-time results appear in your terminal
   - Logs are saved to `/path/to/checkfiles/logs/`

### Validating S3 Files

1. Navigate to the checkfiles directory:
   ```bash
   cd /path/to/checkfiles
   ```

2. Build the container (if you haven't already built it):
   ```bash
   docker compose -f docker/docker-compose.yml build
   ```
   Note: Ensure Docker Engine (Docker Desktop on Mac) is running before executing this command.

3. Make sure your AWS credentials are set up (see Prerequisites)

4. Run the validation command:
   ```bash
   docker compose -f docker/docker-compose.yml run checkfiles -f fastq -s3 s3://your-bucket/path/to/file.fastq.gz
   ```

   **Flag explanation:**
   - `-f fastq`: Specifies the file format. Only three formats are supported: fastq, h5, or h5ad
   - `-s3 s3://bucket/path`: Path to your S3 file(s)

   **Multiple files:** To validate multiple S3 files at once, provide comma-separated paths (no spaces):
   ```bash
   docker compose -f docker/docker-compose.yml run checkfiles -f fastq -s3 "s3://bucket/file1.fastq.gz,s3://bucket/file2.fastq.gz"
   ```

## Example Output

When validation completes, you'll see output similar to:

```
=== Validation Summary ===
Total files: 1
Successfully processed: 1
Valid files: 1
Invalid files: 0
Failed to process: 0

=== Detailed Results ===
/path/to/your_file.fastq.gz: Valid
  File size: 358420 bytes
  MD5: abc123...
```

## Destroying Containers

When you're done using the container:

1. Stop and remove containers:
   ```bash
   docker compose -f docker/docker-compose.yml down
   ```

2. To completely remove all related containers, images, and volumes:
   ```bash
   docker compose -f docker/docker-compose.yml down -v --rmi all
   ```

3. If you need to rebuild the container from scratch (ignoring cache):
   ```bash
   docker compose -f docker/docker-compose.yml build --no-cache
   ```

These commands should be run from the `/path/to/checkfiles` directory, not from inside the `docker` directory.