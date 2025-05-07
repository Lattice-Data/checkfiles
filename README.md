[![Coverage Status](https://coveralls.io/repos/github/Lattice-Data/checkfiles/badge.svg?branch=main)](https://coveralls.io/github/Lattice-Data/checkfiles?branch=main)

# Checkfiles

A scalable system for processing and validating files. It supports both local validation via Docker containers and AWS cloud-based architecture. This project provides infrastructure and automation for validation workflows.

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

Checkfiles is a system that supports both local and cloud-based deployments:
- Supports both local validation via Docker containers and cloud-based deployment.
- Monitors for new file uploads
- Processes and validates files (FASTQ, H5, H5AD formats supported)
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

**Note**: The AWS Step Functions instructions below are intended only for advanced users who need to deploy a new Step Function for file validation. Lattice curators should follow the validation execution instructions in `docker/README.md` or `cdk/README.md` instead of deploying AWS Step Function.

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
  "query": "/report/?type=RawSequenceFile&lab.title=Calliope+Dendrou%2C+Oxford&read_type=i5+index",
  "instance_name_suffix": "mike",
  "backend_uri": "https://www.lattice-data.org/",
  "update": false
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
| `--backend-uri` | URI of backend service | `--backend-uri https://api.example.com` |
| `--query` | Query string for backend | `--query "type=file&format=fastq"` |
| `--update` | Update backend with results | `--update` |

### Docker-specific Options

When using Docker, paths inside the container start with `/app`:

```bash

# Using host path (automatically translated)
docker compose -f docker/docker-compose.yml run checkfiles -f fastq -l /Users/yourusername/path/to/file.fastq
```


## Supported File Formats

Checkfiles currently supports the following file formats:

- **FASTQ**: DNA/RNA sequence reads (`.fastq`, `.fq`, with optional `.gz` compression)
- **H5**: Hierarchical data format (`.h5`)
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



### Testing
```bash
# Run unit tests
python -m pytest src/tests/
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