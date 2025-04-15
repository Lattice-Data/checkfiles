# Packer AMI Builder for Checkfiles

This Packer configuration builds an Ubuntu 22.04 AMI for the Checkfiles application. The AMI includes all necessary dependencies and configurations to run the Checkfiles application in AWS.

## Prerequisites

- [Packer CLI](https://developer.hashicorp.com/packer/tutorials/docker-get-started/get-started-install-cli) installed on your system
- AWS CLI configured with appropriate credentials
- AWS IAM permissions to create and manage EC2 instances and AMIs
- Amazon EBS volume creation permissions

## Dependencies

Install the required Packer plugins:
```bash
packer plugins install github.com/hashicorp/amazon
```

## Configuration

1. Open `checkfiles_ubuntu_2204_variables.json` and set the following variables:
   - `aws_profile_name`: The name of your AWS profile (should match the profile name in `~/.aws/credentials`)
   - Review and adjust other variables as needed for your environment

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

## Cleanup

The temporary EC2 instance is automatically terminated after the AMI creation. However, you may want to:
- Delete the AMI if it's no longer needed
- Clean up any associated snapshots

## Support

For additional help or issues, please refer to:
- [Packer Documentation](https://developer.hashicorp.com/packer/docs)
- [AWS Documentation](https://docs.aws.amazon.com/)