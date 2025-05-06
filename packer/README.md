## Packer Configuration for Checkfiles

This directory contains the Packer configuration files used to build the AWS AMI (Amazon Machine Image) for the Checkfiles system.

### Overview

The Checkfiles AMI builds an AWS EC2 image with the necessary software to validate file formats like FASTQ and HDF5. The AMI is designed to work with direct S3 streaming, eliminating the need for mounting S3 buckets or local storage.

### Components

- `packer.json`: Main Packer configuration file
- `scripts/`: Installation scripts for the AMI
  - `install_dependencies.sh` - Installs base dependencies
  - `install_python.sh` - Installs Python 3.9
  - `install_aws_cli.sh` - Installs AWS CLI v2
  - `create_validator_stubs.sh` - Creates validation module stubs
  - `setup_logging.sh` - Sets up logging directories
  - `cleanup.sh` - Cleans up temporary files

### Included Software

- Python 3.9 with required packages
- AWS CLI v2 for S3 access
- Validation libraries:
  - `validators.fastq`: FASTQ file validator
  - `validators.hdf5`: HDF5 file validator
  - `validators.h5ad`: H5AD file validator

### Usage

To build the AMI:

```bash
cd packer
packer build packer.json
```

To customize the build:

```bash
packer build \
  -var 'aws_region=us-west-2' \
  -var 'instance_type=t3.medium' \
  packer.json
```

### Variables

- `aws_region`: AWS region to build in (default: us-east-1)
- `instance_type`: EC2 instance type for the build process (default: t3.micro)
- `ami_name`: Name prefix for the created AMI (default: checkfiles)

### Deployment

Once the AMI is built, it can be used to launch EC2 instances for file validation. The instances can be configured with:

1. IAM role with S3 access
2. Environment variables for backend authentication
3. User data script to start the validation service