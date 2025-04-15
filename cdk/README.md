# Checkfiles Step Function Deployment

This CDK (Cloud Development Kit) project deploys a Step Function workflow for the Checkfiles application. The Step Function orchestrates various AWS services to process and validate files according to the Checkfiles application requirements.

## ⚠️ Warning

If you are not sure this is what you should be running, you should not be running it. This deployment affects production resources.

## Prerequisites

- Node.js (v18 or later)
- Python 3.11
- AWS CLI configured with appropriate credentials
- AWS CDK CLI
- Required AWS permissions for deploying Step Functions and related resources

## System Requirements

- Operating System: Linux, macOS, or Windows
- Minimum 4GB RAM
- 2GB free disk space

## Installation

1. Install AWS CDK (version 2.189.0):
   ```bash
   npm install -g aws-cdk@2.189.0
   ```

2. Create and activate Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Stack Structure

The CDK stack includes:
- Step Function definition
- IAM roles and policies
- CloudWatch alarms and metrics
- S3 bucket configurations
- Lambda function integrations

## Deployment

To deploy the stack:

```bash
cdk deploy RunCheckfilesStepFunctionSandbox --profile lattice-prod
```

### Deployment Options

- `--profile`: Specify AWS profile (default: lattice-prod)
- `--require-approval`: Enable manual approval for sensitive changes
- `--context`: Set context variables

## Testing

After deployment:
1. Verify Step Function state machine is created
2. Check CloudWatch logs for any errors
3. Test the Step Function with sample input

## Monitoring

Monitor the deployment using:
- CloudWatch Metrics
- Step Function execution history
- CloudWatch Logs

## Troubleshooting

Common issues and solutions:

1. **Deployment Failures**
   - Check AWS credentials and permissions
   - Verify all prerequisites are installed
   - Review CloudFormation stack events

2. **Step Function Errors**
   - Check CloudWatch logs
   - Verify IAM permissions
   - Review Step Function execution history

3. **Resource Limits**
   - Check AWS service quotas
   - Verify region-specific limitations

## Cleanup

To remove the stack:

```bash
cdk destroy RunCheckfilesStepFunctionSandbox --profile lattice-prod
```

## Support

For additional help:
- AWS CDK Documentation: https://docs.aws.amazon.com/cdk/
- AWS Step Functions Documentation: https://docs.aws.amazon.com/step-functions/
- Contact the development team for specific issues
