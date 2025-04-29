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

This directory contains Packer templates and scripts to build the AWS AMI used by the checkfiles application.

## Updates (Important)

**April 2025 Update**: Fixed critical module path structure issues in the AMI. The scripts now correctly set up the validators modules in the expected `src/validators/fastq` structure rather than just `validators/fastq`, resolving import errors in the runtime environment.

## Requirements

- [Packer](https://www.packer.io/downloads)
- AWS CLI configured with appropriate permissions
- Python 3.10+

## Directory Structure

```
.
├── README.md
├── scripts/                  # Scripts for setting up the AMI
│   ├── create_validator_stubs.sh
│   ├── debug_fuse.sh
│   ├── goofys_mount.sh
│   ├── install_python_dependencies.sh
│   ├── install_samtools.sh
│   ├── setup_validator_modules.sh
│   └── validate_ami.sh
└── templates/                # Packer templates
    ├── build_AMI.pkr.hcl
    └── checkfiles_ubuntu_2204_variables.json
```

## Building the AMI

1. Ensure all code changes are committed to the repository
2. Navigate to the packer directory
3. Run the build command:

```bash
cd packer
packer build -var-file=templates/checkfiles_ubuntu_2204_variables.json templates/build_AMI.pkr.hcl
```

## Deploying the New AMI

After building the new AMI, you'll need to update the CDK deployment to use the new AMI ID:

1. Update the AMI ID in the CDK configuration file:

```bash
# Navigate to the CDK directory
cd ../cdk

# Update the AMI ID in the appropriate configuration file
# The file location might vary depending on your setup
```

2. Deploy the updated CDK stack:

```bash
cdk deploy checkfiles-runner-stack
```

## Troubleshooting

### Common Issues

#### Import Error: `No module named 'src.validators.fastq'`

This indicates a mismatch between the code's import expectations and the module structure in the AMI. The recent update should fix this issue by creating the correct directory structure. If you're still experiencing this issue:

1. Verify that the scripts in the `packer/scripts` directory are correctly setting up the module structure
2. Ensure the AMI is being built with the latest scripts
3. Verify that the CDK stack is using the new AMI ID

#### Validator Methods Missing

If you encounter errors about missing methods (like `validate_stream`), make sure the validator stubs in `create_validator_stubs.sh` include all required methods with the correct signatures.

## Testing the AMI

You can test the AMI functionality directly before deploying:

1. Launch an EC2 instance using the new AMI
2. Connect to the instance using SSH
3. Run the verification script:

```bash
cd /opt/checkfiles
python -c "from src.validators.fastq import FastqValidator; print('Import successful')"
validator = FastqValidator()
print(hasattr(validator, 'validate_stream'))
```

## Contact

For questions or issues, please contact the checkfiles team.