# AWS Step Function Guide for Checkfiles

This guide explains how to run (execute) a deployed AWS Step Function of Checkfiles. This method is recommended for processing files submitted to the Lattice data portal.

## Table of Contents
- [What is AWS Step Functions?](#what-is-aws-step-functions)
- [Running (executing) Deployed Step Functions](#running-executing-deployed-step-functions)
- [Monitoring and Logs](#monitoring-and-logs)
- [Checkfiles Step Function Deployment](#checkfiles-step-function-deployment)
- [Advanced Configuration](#advanced-configuration)

## What is AWS Step Functions?

AWS Step Functions is a serverless workflow service that lets you coordinate multiple AWS services into business-critical applications. For Checkfiles, it:

- Orchestrates the file validation process
- Manages scaling based on number of files to be validated
- Handles error conditions automatically
- Provides detailed logs and metrics

## Running (executing) Deployed Step Functions

### Step 1: Open the AWS Console

1. Log in to the [AWS Management Console](https://console.aws.amazon.com/)
2. Navigate to the Step Functions service
   - Type "Step Functions" in the search bar
   - Or find it under "Services" > "Application Integration" > "Step Functions"

### Step 2: Find Your State Machine

1. In the Step Functions dashboard, click on "State machines"
2. Look for "RunCheckfilesStateMachine" in the list
   > **Note:** If you don't see any state machines, check that you are in the **us-west-1** region in the top right corner of the AWS console
3. Click on the state machine name

### Step 3: Start a New Execution

1. Click the "Start execution" button
2. Enter execution input in JSON format:

```json
{
  "query": "/search/?type=RawSequenceFile&validated=false",
  "instance_name_suffix": "idan-1",
  "backend_uri": "https://www.lattice-data.org/",
  "update": false
}
```

> **Important:** The AWS Step Function is designed to run on files located in the Lattice data portal, not on local or directly specified S3 files. Use the `query` and `backend_uri` parameters to specify which files to validate. The system will automatically extract file-specific metadata such as file format and S3 path.

3. (Optional) Enter a custom execution name or use the auto-generated one
4. Click "Start execution"

### Common Parameters

When starting a Step Function execution, you can provide these parameters:

| Parameter | Type | Description | Required | Example |
|-----------|------|-------------|----------|---------|
| query | String | Query string to find files to validate | Yes | "/search/?type=RawSequenceFile&validated=false" |
| instance_name_suffix | String | Suffix for the EC2 instance name | Yes | "idan-1" |
| backend_uri | String | URI of the Lattice data portal | Yes | "https://www.lattice-data.org/" |
| update | Boolean | Update backend with validation results | No | false |

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

5. The progress of the validation will also be reflected by the checkfiles-bot in the Slack channel named #checkfiles, providing real-time updates as files are processed

## Monitoring and Logs

### Viewing CloudWatch Logs

Step Function executions generate logs that can be viewed in CloudWatch:

1. Open the [CloudWatch Console](https://console.aws.amazon.com/cloudwatch/)
2. Navigate to "Log groups" in the left sidebar
3. Find log groups with names containing:
   - `checkfiles-log` (EC2 instance logs)
   - `/aws/states/RunCheckfilesStateMachine` (Step Function execution logs)

4. Click on a log group, then click on the most recent log stream
5. Use the search bar to filter logs for specific information

## Checkfiles Step Function Deployment

**IMPORTANT NOTE**: The following deployment instructions are intended only for advanced users who need to create their own instance of the Step Function. Most users should only need to execute an existing deployment as described in the "Running (executing) Deployed Step Functions" section above.

Before you begin, ensure you have:

- AWS Account with appropriate permissions

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

- AWS CLI installed and configured. Choose ONE of these installation methods:
  ```bash
  # Option 1: Install AWS CLI with conda (recommended)
  conda install -c conda-forge awscli
  
  # Option 2: macOS with Homebrew
  brew install awscli
  
  # To verify installation:
  aws --version
  # Expected output: aws-cli/2.x.x Python/3.x.x ... 
  ```

- Node.js v18+ installed. Choose ONE of these installation methods:
  ```bash
  # Option 1: macOS with Homebrew
  brew install node@18
  
  # OR
  
  # Option 2: Using nvm (Node Version Manager)
  # Step 1: Install nvm if you don't have it
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
  # Step 2: Install and use Node.js v18
  nvm install 18
  nvm use 18
  
  # To verify installation (after using either option):
  node --version
  # Expected output: v18.x.x or higher
  ```

- AWS CDK v2.1007.0+ installed. Choose ONE of these installation methods:
  ```bash
  # Option 1: Install with npm (standard method)
  npm install -g aws-cdk@2.1007.0
  
  # OR
  
  # Option 2: If npm is not available
  # Download the CDK binary directly from GitHub:
  # https://github.com/aws/aws-cdk/releases
  # After downloading:
  # 1. Unzip the downloaded file
  # 2. Make the binary executable:
  #    chmod +x cdk
  # 3. Move the binary to a directory in your PATH:
  #    sudo mv cdk /usr/local/bin/
  
  # OR
  
  # Option 3: Install via conda
  conda install -c conda-forge aws-cdk-lib=2.1007.0
  
  # To verify installation (after using any option):
  cdk --version
  # Expected output: 2.1007.0 (build ...)
  ```

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
- Default region (e.g., us-west-1)
- Default output format (json recommended)

### Step 3: Deploy the Step Function

```bash
# Make sure you're in the cdk directory
cd checkfiles/cdk

# Deploy to production (replace with your AWS profile if necessary)
cdk deploy RunCheckfilesStepFunctionProduction --profile your-profile-name
# Note: For Lattice AWS profile use --profile lattice-prod
```

The deployment process:
1. Creates AWS resources (Step Functions, Lambda functions, IAM roles, etc.)
2. Shows deployment progress in the terminal
3. Outputs the ARN of the Step Function when complete

The deployment will take approximately 5-10 minutes. When it's done, you'll see output like:

```
✅ RunCheckfilesStepFunctionProduction

Outputs:
RunCheckfilesStepFunctionProduction.StateMachineArn = arn:aws:states:us-west-1:123456789012:stateMachine:RunCheckfilesStateMachine
```

Make note of this ARN as you'll need it for the next steps.

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

