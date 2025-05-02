[![Coverage Status](https://coveralls.io/repos/github/Lattice-Data/checkfiles/badge.svg?branch=cdk-step-function)](https://coveralls.io/github/Lattice-Data/checkfiles?branch=cdk-step-function)

# Checkfiles

A scalable system for processing and validating file uploads in a cloud environment. This project provides infrastructure and automation for file processing workflows.


## Overview

Checkfiles is a cloud-based system that:
- Monitors for new file uploads
- Processes and validates files
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

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Python 3.x
- Node.js and npm (for CDK)
- Packer (for AMI building)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/checkfiles.git
   cd checkfiles
   ```

2. Install dependencies:
   ```bash
   # Install Python dependencies
   pip install -r requirements.txt

   # Install CDK dependencies
   cd cdk
   npm install
   ```

3. Configure AWS credentials:
   ```bash
   aws configure
   ```

## Deployment

### Infrastructure Deployment
```bash
cd cdk
cdk deploy
```

### AMI Building
```bash
cd packer
packer build checkfiles.json
```

## Configuration

### Environment Variables
- `PORTAL_SECRETS_ARN`: ARN of the secrets containing portal credentials
- `BACKEND_URI`: Base URI of the backend service

### AWS Resources
- SQS Queues for message processing
- CloudWatch Events for scheduling
- IAM Roles and Policies
- VPC Configuration
- Security Groups

## Development

### Local Development
1. Set up virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

### Testing
```bash
# Run unit tests
pytest

# Run integration tests
pytest tests/integration

# Run linting
flake8
```

## Monitoring

### CloudWatch
- Logs for each Lambda function
- Metrics for processing performance
- Alarms for error conditions

### Custom Metrics
- Files processed per minute
- Processing time
- Error rates
- Queue lengths

## Security

### IAM
- Least privilege principle
- Role-based access control
- Secure credential management

### Network
- VPC isolation
- Security groups
- Private subnets

### Data
- Encryption at rest
- Encryption in transit
- Secure secret management

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

## Roadmap

- [ ] Enhanced monitoring capabilities
- [ ] Additional file format support
- [ ] Performance optimizations
- [ ] Extended test coverage

## Supported File Formats

Checkfiles can validate various file formats including:

- FASTQ (DNA/RNA sequence reads)
- BAM (Binary Alignment Map)
- CRAM (Compressed Reference-oriented Alignment Map)
- And more...

Each file type has specific validators that check for format compliance, data integrity, and other format-specific requirements.