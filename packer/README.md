# Packer AMI Builder for Checkfiles

This Packer configuration builds an Ubuntu 22.04 AMI for the Checkfiles application. The AMI includes all necessary dependencies and configurations to run the Checkfiles application in AWS.

## Prerequisites

- [Packer CLI](https://developer.hashicorp.com/packer/tutorials/docker-get-started/get-started-install-cli) (v1.9.0+) installed on your system
- AWS CLI configured with appropriate credentials
- AWS IAM permissions to create and manage EC2 instances and AMIs
- Amazon EBS volume creation permissions

## Dependencies

Install the required Packer plugins:
```bash
packer plugins install github.com/hashicorp/amazon
```

## Configuration

1. Open `templates/checkfiles_ubuntu_2204_variables.json` and set the following variables:
   - `aws_profile_name`: The name of your AWS profile (should match the profile name in `~/.aws/credentials`)
   - Review and adjust other variables as needed for your environment

## Installed Components

The AMI includes the following main components:

- Ubuntu 22.04 LTS (Jammy Jellyfish)
- Python 3.x with type hints and proper documentation
- AWS CLI v1.29.17 with botocore v1.31.17 and boto3 v1.28.17
- Goofys for S3 file mounting
- Samtools v1.17 for BAM/CRAM file validation
- Development tools: pytest, black, ruff, mypy
- Additional system dependencies

## Python Validation Modules

The AMI includes properly documented Python validation modules following Google Python Style Guide:

- `validators.fastq`: FASTQ file validator with Rust-based implementation
- `validators.bam`: BAM file validator using samtools
- Additional validator modules as needed

All modules include:
- Comprehensive type hints
- Google-style docstrings
- Proper error handling and logging
- Unit tests with 80%+ coverage target

## Installation Scripts

The following installation scripts are included:

- `scripts/install_python_dependencies.sh`: Installs Python packages and dependencies
- `scripts/setup_validator_modules.sh`: Sets up validator module structure
- `scripts/create_validator_stubs.sh`: Creates properly documented validator stubs
- `scripts/install_samtools.sh`: Installs samtools with proper error handling
- `scripts/install_goofys_and_validatefiles.sh`: Installs S3 mounting utilities

## Building the AMI

1. Navigate to the `templates` directory:
   ```bash
   cd templates
   ```

2. Build the AMI:
   ```bash
   packer build --var-file="checkfiles_ubuntu_2204_variables.json" build_AMI.pkr.hcl
   ```

The build process will:
- Launch a temporary EC2 instance
- Install and configure all required software
- Create an AMI from the configured instance
- Terminate the temporary instance

## Output

After successful completion, Packer will output:
- The AMI ID of the newly created image
- The region where the AMI was created
- Any additional resources created during the build

## Troubleshooting

Common issues and solutions:

1. **Authentication Errors**
   - Verify your AWS credentials are correctly configured
   - Check that the `aws_profile_name` matches your AWS profile

2. **Permission Errors**
   - Ensure your IAM user has the necessary permissions
   - Check your AWS CLI configuration

3. **Build Failures**
   - Check the Packer logs for detailed error messages
   - Verify all required variables are set correctly
   - Check installation script logs in `/tmp/*.log`

4. **Python Module Errors**
   - Verify Python dependencies were installed correctly
   - Check module import paths

## Cleanup

The temporary EC2 instance is automatically terminated after the AMI creation. However, you may want to:
- Delete the AMI if it's no longer needed
- Clean up any associated snapshots

## Support

For additional help or issues, please refer to:
- [Packer Documentation](https://developer.hashicorp.com/packer/docs)
- [AWS Documentation](https://docs.aws.amazon.com/)
- [Project Repository](https://github.com/yourusername/checkfiles)

# Checkfiles AMI Builder

This directory contains the Packer configuration and scripts for building the Checkfiles AMI.

## Overview

The Checkfiles AMI builds an AWS EC2 image with the necessary software to validate file formats like FASTQ, BAM, HDF5, etc. The AMI is designed to work with direct S3 streaming, eliminating the need for mounting S3 buckets or local storage.

## Recent Updates

As of the latest version, the following changes have been made:

- Removed goofys S3 mount functionality as it's no longer needed
- Removed validateFiles binary as it's been replaced by Python-based validators
- Simplified installation scripts to focus on core validation functionality
- Updated validator modules to work directly with S3 streaming APIs

## Building the AMI

To build the AMI:

1. Ensure you have Packer installed
2. Configure AWS credentials
3. Run the build command:

```bash
cd packer/templates
packer build -var-file=checkfiles_ubuntu_2204_variables.json ./checkfiles_ubuntu_2204.json
```

## Included Scripts

- `install_base_checkfiles_packages.sh` - Installs base system packages
- `install_samtools.sh` - Installs samtools for BAM validation
- `install_python_dependencies.sh` - Installs Python packages
- `setup_validator_modules.sh` - Sets up Python validation modules
- `create_validator_stubs.sh` - Creates stub implementations of validators
- `setup_environment_file.sh` - Sets up environment variables
- `validate_ami.sh` - Validates the AMI configuration

## Architecture

The Checkfiles application now uses direct S3 streaming for validation:

1. Application receives a file to validate (either local or S3)
2. If it's an S3 file, it streams the content directly using boto3
3. Content is passed through validators without storing on disk
4. Validation results, stats, and hash values are returned

This approach improves performance, reduces storage requirements, and eliminates the need for FUSE mounts like goofys.

## Contact

For questions or issues, please contact the checkfiles team.