# Checkfiles Lambda Functions

This directory contains AWS Lambda functions that work together to manage and process file checks in the Checkfiles system. Each Lambda function serves a specific purpose in the workflow.

## Lambda Functions

### 1. check_pending
- **Purpose**: Checks for pending files that need processing
- **Trigger**: Scheduled CloudWatch Event
- **Functionality**:
  - Queries the backend for pending files
  - Returns the number of files pending for processing
  - Used to determine if additional processing is needed

### 2. create_instance
- **Purpose**: Creates new instances for file processing
- **Trigger**: SQS Queue
- **Functionality**:
  - Spins up new processing instances
  - Configures necessary resources
  - Initializes processing environment

### 3. run_checkfiles
- **Purpose**: Executes the actual file checking process
- **Trigger**: SQS Queue
- **Functionality**:
  - Processes individual files
  - Runs validation checks
  - Updates file status

### 4. get_status
- **Purpose**: Retrieves and reports the status of file processing
- **Trigger**: API Gateway
- **Functionality**:
  - Provides status information about file processing
  - Returns current state of processing jobs
  - Used for monitoring and reporting

### 5. counter
- **Purpose**: Tracks and manages processing counts
- **Trigger**: SQS Queue
- **Functionality**:
  - Maintains counters for processed files
  - Updates statistics
  - Provides metrics for monitoring

## Environment Variables

The following environment variables are required for proper functioning:

- `PORTAL_SECRETS_ARN`: ARN of the secrets containing portal credentials
- `BACKEND_URI`: Base URI of the backend service

## Development

### Prerequisites
- AWS CDK
- Python 3.x
- AWS CLI configured with appropriate credentials

### Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables in your deployment environment

3. Deploy using CDK:
   ```bash
   cdk deploy
   ```

## Testing
Each Lambda function includes unit tests. Run tests using:
```bash
python -m pytest
```

## Monitoring
- CloudWatch Logs for each Lambda function
- CloudWatch Metrics for performance tracking
- SQS Queue monitoring for message processing

## Security
- IAM roles with least privilege principle
- Secrets stored in AWS Secrets Manager
- Environment variables for configuration
- VPC configuration for network isolation

## Error Handling
- Comprehensive error logging
- Dead Letter Queues for failed messages
- Retry mechanisms for transient failures

## Contributing
1. Create a feature branch
2. Make your changes
3. Run tests
4. Submit a pull request

