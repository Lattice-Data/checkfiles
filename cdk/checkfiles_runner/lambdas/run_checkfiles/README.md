# Checkfiles Runner Lambda

This Lambda function is responsible for invoking the checkfiles tool on EC2 instances to validate file formats.

## Overview

The Lambda function does the following:

1. Sets up the Python environment on the target EC2 instance
2. Ensures proper PYTHONPATH settings
3. Runs the checkfiles command with appropriate parameters
4. Captures and logs the output

## Deployment

The Lambda is packaged and deployed via the GitHub Actions workflow defined in `.github/workflows/deploy-lambda.yml`. The deployment includes:

1. The Lambda handler code (main.py)
2. Core utility modules from the src/utils/helpers directory

## Configuration

The Lambda expects the following environment variables:

- `PORTAL_SECRETS_ARN`: ARN of the secrets manager containing portal credentials
- `BACKEND_URI`: URI for the backend API

## Input Parameters

The Lambda handler expects the following parameters in the event object:

- `instance_id`: EC2 instance ID to run the command on
- `backend_uri`: Backend API URI
- `instance_name_suffix`: Suffix for the instance name
- `query`: Query string for the checkfiles tool
- `iterator`: Iterator value for step functions
- `update` (optional): Whether to run in update mode (default: false)
- `number_of_files_pending` (optional): Number of files pending validation

## Output

The Lambda returns an object containing:

- `instance_id`: EC2 instance ID
- `command_id`: SSM command ID for tracking execution
- `update`: Whether update mode was enabled
- `iterator`: Iterator value passed through
- `backend_uri`: Backend URI passed through
- `instance_name_suffix`: Instance name suffix passed through
- `query`: Query passed through
- `number_of_files_pending`: Number of files pending passed through

## Error Handling

The Lambda will log errors to CloudWatch and attempt to continue execution where possible.

## Testing

To test the Lambda locally, you can use the AWS SAM CLI or set up a local environment with similar configuration to the EC2 instances. 