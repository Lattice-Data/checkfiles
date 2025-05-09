# AWS Step Function Guide for Checkfiles

This guide explains how to deploy and use the Checkfiles application using AWS Step Functions. This method is recommended for production environments and processing large numbers of files.

## Table of Contents
- [What is AWS Step Functions?](#what-is-aws-step-functions)
- [Prerequisites](#prerequisites)
- [Installation Guide](#installation-guide)
- [Using Step Functions](#using-step-functions)
- [Monitoring and Logs](#monitoring-and-logs)
- [Common Parameters](#common-parameters)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## What is AWS Step Functions?

AWS Step Functions is a serverless workflow service that lets you coordinate multiple AWS services into business-critical applications. For Checkfiles, it:

- Orchestrates the file validation process
- Manages scaling based on number of files to be validated
- Handles error conditions automatically
- Provides detailed logs and metrics

## Prerequisites

Before you begin, ensure you have:

- AWS Account with appropriate permissions to create and manage:
  - Step Functions
  - Lambda functions
  - IAM roles
  - CloudWatch logs
  - S3 bucket access

- AWS CLI installed and configured. You can install it using:
  ```bash
  # macOS with Homebrew
  brew install awscli
  
  # Linux/macOS with pip
  pip install awscli
  
  # To verify installation:
  aws --version
  # Expected output: aws-cli/2.x.x Python/3.x.x ... 
  ```

- Conda installed for managing Python environments:
  ```bash
  # To verify conda installation:
  conda --version
  # Expected output: conda x.x.x
  
  # Create a conda environment with Python 3.11
  conda create -n checkfiles python=3.11
  
  # Activate the environment
  conda activate checkfiles
  
  # To verify Python version:
  python --version
  # Expected output: Python 3.11.x
  ```

- Node.js v18+ installed:
  ```bash
  # To verify installation:
  node --version
  # Expected output: v18.x.x or higher
  ```

- AWS CDK v2.1007.0+ installed:
  ```bash
  # Install with npm (standard method)
  npm install -g aws-cdk@2.1007.0
  
  # Alternative method if npm is not available:
  # 1. Download the CDK binary directly from GitHub:
  # https://github.com/aws/aws-cdk/releases
  
  # 2. Or install via pip (limited functionality):
  conda install -c conda-forge aws-cdk-lib=2.1007.0
  
  # To verify installation:
  cdk --version
  # Expected output: 2.1007.0 (build ...)
  ```

## Installation Guide

### Step 1: Set Up Environment

This guide assumes you have already cloned the repository as described in the main [README.md](../README.md).

```bash
# Navigate to the cdk directory
cd checkfiles/cdk

# If using conda (recommended):
conda activate checkfiles

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure AWS Credentials

If you haven't configured AWS CLI already:

```bash
aws configure
```

You'll be prompted to enter:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., us-west-2)
- Default output format (json recommended)

### Step 3: Deploy the Step Function

```bash
# Make sure you're in the cdk directory
cd cdk

# Deploy to production (replace with your AWS profile if necessary)
cdk deploy RunCheckfilesStepFunctionProduction --profile your-profile-name
```

The deployment process:
1. Creates AWS resources (Step Functions, Lambda functions, IAM roles, etc.)
2. Shows deployment progress in the terminal
3. Outputs the ARN of the Step Function when complete

The deployment will take approximately 5-10 minutes. When it's done, you'll see output like:

```
✅ RunCheckfilesStepFunctionProduction

Outputs:
RunCheckfilesStepFunctionProduction.StateMachineArn = arn:aws:states:us-west-2:123456789012:stateMachine:RunCheckfilesStepFunctionProduction
```

Make note of this ARN as you'll need it for the next steps.

## Using Step Functions

### Step 1: Open the AWS Console

1. Log in to the [AWS Management Console](https://console.aws.amazon.com/)
2. Navigate to the Step Functions service
   - Type "Step Functions" in the search bar
   - Or find it under "Services" > "Application Integration" > "Step Functions"

### Step 2: Find Your State Machine

1. In the Step Functions dashboard, click on "State machines"
2. Look for "RunCheckfilesStepFunctionProduction" in the list
3. Click on the state machine name

### Step 3: Start a New Execution

1. Click the "Start execution" button
2. Enter execution input in JSON format:

```json
{
  "file_s3_uri": "s3://your-bucket/path/to/file.fastq.gz",
  "file_format": "fastq",
  "debug": true,
  "threads": 4
}
```

3. (Optional) Enter a custom execution name or use the auto-generated one
4. Click "Start execution"

### Step 4: Monitor the Execution

Once started, you'll see a visualization of the workflow:

1. Each step is represented as a box in the workflow diagram
2. Steps change color to indicate their status:
   - In progress: Blue
   - Succeeded: Green
   - Failed: Red

3. The execution details panel shows:
   - Execution status
   - Start and end times
   - Input/output data

4. Click on individual steps to see details about that specific step

## Monitoring and Logs

### Viewing CloudWatch Logs

Step Function executions generate logs that can be viewed in CloudWatch:

1. Open the [CloudWatch Console](https://console.aws.amazon.com/cloudwatch/)
2. Navigate to "Log groups" in the left sidebar
3. Find log groups with names containing:
   - `/aws/lambda/RunCheckfiles` (Lambda function logs)
   - `/aws/states/RunCheckfilesStepFunction` (Step Function execution logs)

4. Click on a log group, then click on the most recent log stream
5. Use the search bar to filter logs for specific information

### Setting Up CloudWatch Alarms (Optional)

You can create alarms to notify you of issues:

1. In the CloudWatch console, go to "Alarms" > "Create alarm"
2. Click "Select metric"
3. Navigate to "States" > "Metrics with no dimensions"
4. Select "ExecutionsFailed" for your state machine
5. Configure the threshold (e.g., alarm when ≥ 1)
6. Set up notifications (e.g., email, SMS)
7. Review and create the alarm

## Common Parameters

When starting a Step Function execution, you can provide these parameters:

| Parameter | Type | Description | Required | Example |
|-----------|------|-------------|----------|---------|
| file_s3_uri | String | S3 URI of the file to validate | Yes | "s3://your-bucket/path/to/file.fastq.gz" |
| file_format | String | Format of the file (fastq, h5, h5ad) | Yes | "fastq" |
| debug | Boolean | Enable detailed debug output | No | true |
| threads | Number | Number of threads to use for validation | No | 4 |
| update | Boolean | Update backend with validation results | No | false |
| update_s3_tags | Boolean | Add validation tags to S3 objects | No | false |
| ignore_active_credentials | Boolean | Skip credential check for backend | No | false |

## Troubleshooting

### Deployment Failures

If the `cdk deploy` command fails:

1. **Check AWS credentials**
   ```bash
   aws sts get-caller-identity
   ```
   This should show your account ID and user. If not, run `aws configure` again.

2. **Verify CDK prerequisites**
   ```bash
   cdk --version
   python --version
   ```
   Ensure CDK version is 2.1007.0+ and Python is 3.11.

3. **Review CloudFormation stack**
   - Open the AWS CloudFormation console
   - Look for stacks with names containing "RunCheckfiles"
   - Check the "Events" tab for error messages

### Execution Failures

If a Step Function execution fails:

1. **Check input parameters**
   - Verify the S3 URI is correct
   - Ensure the file format is supported
   - Check file permissions in S3

2. **Review logs in CloudWatch**
   - Find the execution ID in the Step Functions console
   - Look for logs with that execution ID in CloudWatch
   - Check for error messages

3. **Verify S3 access**
   - Confirm the Step Function has permissions to access the S3 bucket
   - Try accessing the file manually with AWS CLI:
     ```bash
     aws s3 ls s3://your-bucket/path/to/file.fastq.gz
     ```

### Common Error Messages

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| "Access Denied" | Insufficient permissions | Check IAM roles and bucket policies |
| "File not found" | Incorrect S3 URI or missing file | Verify the file exists in S3 |
| "Unsupported file format" | Format not recognized | Use one of: fastq, h5, h5ad |
| "Validation failed" | File does not meet format requirements | Check file contents and integrity |
| "Execution timed out" | File too large or process too slow | Increase timeout settings or use a smaller file |

## Advanced Configuration

For advanced users who need to modify the Step Function:

### Updating the CDK Stack

```bash
# Make changes to the CDK code (app.py or checkfiles_runner/)
# Then deploy the changes
cdk deploy RunCheckfilesStepFunctionProduction --profile your-profile-name
```

### Cleaning Up Resources

To remove all deployed resources:

```bash
cdk destroy RunCheckfilesStepFunctionProduction --profile your-profile-name
```

**⚠️ Warning:** This will permanently delete all resources created by the CDK stack, including logs and metrics.

### Configuring Timeout and Retry Settings

To change timeout or retry settings, modify the Step Function definition in `checkfiles_runner/step_functions.py`.
