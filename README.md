[![Coverage Status](https://coveralls.io/repos/github/Lattice-Data/checkfiles/badge.svg?branch=main)](https://coveralls.io/github/Lattice-Data/checkfiles?branch=main)

# Checkfiles

A scalable system for processing and validating file uploads in a cloud environment. This project provides infrastructure and automation for file processing workflows.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Running Checkfiles](#running-checkfiles)
  - [Using Docker (Easiest Method)](#using-docker-easiest-method)
  - [Using AWS Step Functions](#using-aws-step-functions)
- [Command Reference](#command-reference)
- [Supported File Formats](#supported-file-formats)
- [Monitoring and Logs](#monitoring-and-logs)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Overview

Checkfiles is a cloud-based system that:
- Monitors for new file uploads
- Processes and validates files (FASTQ, HDF5, H5AD formats supported)
- Tracks processing status
- Provides metrics and monitoring
- Scales automatically based on workload

## Architecture

The system consists of several components:

### 1. AWS Lambda Functions (`cdk/checkfiles_runner/lambdas/`)
- `check_pending`: Monitors for pending files
- `create_instance`: Manages processing instances
- `run_checkfiles`: Executes file validation
- `get_status`: Provides status information
- `counter`: Tracks processing metrics

### 2. Infrastructure (`cdk/`)
- AWS CDK-based infrastructure as code
- Automated deployment pipelines
- Resource management and scaling

### 3. AMI Builder (`packer/`)
- Custom AMI creation for processing instances
- Environment configuration
- Dependency management

### 4. Source Code (`src/`)
- Core processing logic
- Utility functions
- Test suites

## Getting Started

### Prerequisites

- For Docker method:
  - Docker Engine installed ([Install Docker](https://docs.docker.com/get-docker/))
  - Docker Compose V2 (version 2.10.0+)
  - No AWS account needed for local file validation

- For AWS Step Functions method:
  - AWS Account with appropriate permissions
  - AWS CLI installed and configured ([Install AWS CLI](https://aws.amazon.com/cli/))
  - Python 3.11 ([Install Python](https://www.python.org/downloads/))
  - Node.js v18+ and npm ([Install Node.js](https://nodejs.org/))
  - AWS CDK CLI v2.1007.0+ (`npm install -g aws-cdk@2.1007.0`)

### Installation

#### Local Installation (Docker Method)

1. Clone the repository:
   ```bash
   git clone https://github.com/Lattice-Data/checkfiles.git
   cd checkfiles
   ```

2. Create test data directory:
   ```bash
   mkdir -p test_data
   # Add your test files to the test_data directory
   ```

#### AWS Installation (CDK Method)

1. Clone the repository:
   ```bash
   git clone https://github.com/Lattice-Data/checkfiles.git
   cd checkfiles/cdk
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure AWS credentials (if not already done):
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Access Key, default region, and output format
   ```

## Running Checkfiles

### Using Docker (Easiest Method)

Docker is the simplest way to run Checkfiles locally without AWS dependencies.

#### Step 1: Build and start Docker container

```bash
# From project root
docker compose -f docker/docker-compose.yml up
```

This will display the help message showing available commands.

#### Step 2: Validate local files

```bash
# Validate a single FASTQ file
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/test_data/your_file.fastq.gz

# Validate multiple files (comma-separated, no spaces)
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l "/app/test_data/file1.fastq.gz,/app/test_data/file2.fastq.gz"
```

#### Step 3: Validate S3 files (requires AWS credentials)

```bash
# First export your AWS credentials
export AWS_ACCESS_KEY_ID=your-key-id
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-west-2

# Then run validation with S3 path
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -s3 s3://your-bucket/path/to/file.fastq.gz
```

#### Step 4: View logs

Logs are saved to the `logs` directory in your project root:
```bash
# View progress log
cat logs/validation_progress.log

# View debug log
cat logs/checkfiles_debug.log
```

### Using AWS Step Functions

The AWS Step Functions method is recommended for production use and large-scale file processing.

#### Step 1: Deploy the CDK stack

```bash
# Navigate to CDK directory
cd cdk

# Deploy the stack
cdk deploy RunCheckfilesStepFunctionProduction --profile your-aws-profile
```

The deployment will take several minutes. When complete, you'll see outputs including the Step Function's ARN.

#### Step 2: Start a Step Function execution

1. Open the AWS Management Console
2. Navigate to Step Functions
3. Find the deployed state machine (named like "RunCheckfilesStepFunctionProduction")
4. Click "Start execution"
5. Enter input parameters in JSON format:

```json
{
  "file_s3_uri": "s3://your-bucket/path/to/file.fastq.gz",
  "file_format": "fastq",
  "debug": true
}
```

6. Click "Start execution"

#### Step 3: Monitor the execution

1. The execution diagram will show progress through the workflow steps
2. Each state will turn green when successful or red if it fails
3. Click on individual states to see input/output data
4. The final state will show validation results

#### Step 4: View logs in CloudWatch

1. Open CloudWatch in the AWS Management Console
2. Navigate to "Log groups"
3. Find log groups with names containing "RunCheckfiles"
4. Click on a log group to view execution logs
5. Filter logs using the search bar for specific information

## Command Reference

### Common Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-f`, `--file-format` | File format to validate | `-f fastq` |
| `-l`, `--local-file` | Local file path(s) | `-l /path/to/file.fastq.gz` |
| `-s3`, `--s3-file` | S3 file URI(s) | `-s3 s3://bucket/file.fastq.gz` |
| `-d`, `--debug` | Enable debug output | `-d` |
| `-t`, `--threads` | Number of processing threads | `-t 4` |
| `-q`, `--quiet` | Suppress progress indicators | `-q` |
| `--backend-uri` | URI of backend service | `--backend-uri https://api.example.com` |
| `--query` | Query string for backend | `--query "type=file&format=fastq"` |
| `--update` | Update backend with results | `--update` |
| `--log-file` | Custom log file path | `--log-file /path/to/log.txt` |

### Docker-specific Options

When using Docker, paths inside the container start with `/app`:

```bash
# Using local file inside container
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /app/test_data/file.fastq

# Using host path (automatically translated)
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /Users/yourusername/path/to/file.fastq
```

### Step Function Input Parameters

Step Functions accept a JSON object with the following parameters:

```json
{
  "file_s3_uri": "s3://your-bucket/path/to/file.fastq.gz", 
  "file_format": "fastq",
  "debug": true,
  "threads": 4,
  "update": false,
  "update_s3_tags": false,
  "ignore_active_credentials": false
}
```

## Supported File Formats

Checkfiles currently supports the following file formats:

- **FASTQ**: DNA/RNA sequence reads (`.fastq`, `.fq`, with optional `.gz` compression)
- **HDF5**: Hierarchical data format (`.h5`)
- **H5AD**: AnnData single-cell genomics data (`.h5ad`)

Each format has specific validators that check for:
- Format compliance
- Data integrity
- Content validation
- Metadata correctness
- Size and compression verification

## Monitoring and Logs

### Docker Logs

When using Docker, logs are saved to:
- `logs/validation_progress.log`: Shows summary of each validation
- `logs/checkfiles_debug.log`: Detailed debug information

### AWS CloudWatch Logs

When using AWS Step Functions, logs are available in CloudWatch:
1. Open the AWS Management Console
2. Navigate to CloudWatch → Log groups
3. Look for groups with names containing:
   - `/aws/lambda/RunCheckfiles`
   - `/aws/states/RunCheckfilesStepFunction`

### Common Log Messages

- `Successfully processed: X` - Number of files processed
- `Valid files: Y` - Number of valid files
- `Invalid files: Z` - Number of invalid files
- `Failed to process: N` - Files that couldn't be processed

## Troubleshooting

### Docker Issues

1. **Permission denied errors**:
   ```bash
   sudo chown -R $(id -u):$(id -g) logs/
   ```

2. **Container fails to start**:
   - Check if Docker daemon is running
   - Verify Docker Compose is installed
   - Ensure ports aren't already in use

3. **AWS credential errors**:
   - Verify you've exported AWS credentials correctly
   - Check region matches your S3 bucket location

### AWS Step Function Issues

1. **Deployment failures**:
   - Check AWS credentials have sufficient permissions
   - Verify CDK version is 2.1007.0 or higher
   - Ensure Python 3.11 is installed

2. **Execution failures**:
   - Check S3 path is correct and accessible
   - Verify file format is supported
   - Look in CloudWatch logs for detailed error messages

3. **Missing logs**:
   - Check log retention settings in CloudWatch
   - Verify Lambda functions have logging permissions

## Development

### Local Development
1. Set up virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

### Testing
```bash
# Run unit tests
pytest

# Run integration tests
pytest tests/integration

# Run linting
flake8
```

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