import json
import os
import boto3
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TWENTY_THREE__HOURS_IN_SECONDS = str(23 * 3600)


def get_secret_arn():
    return os.environ['PORTAL_SECRETS_ARN']


def get_backend_uri():
    return os.environ['BACKEND_URI']


def run_checkfiles_command(event, context):
    """Run checkfiles command on EC2 instance.
    
    This function sets up the environment on the target EC2 instance
    and runs the checkfiles command with the specified parameters.
    
    Args:
        event: Lambda event containing parameters
        context: Lambda context
        
    Returns:
        Dictionary with execution details
    """
    # Log parameters clearly
    logger.info(f"Event parameters: {json.dumps(event)}")
    logger.info(f"EC2 instance ID: {event['instance_id']}")
    
    # Required parameters
    instance_id = event['instance_id']
    backend_uri = event['backend_uri']
    instance_name_suffix = event['instance_name_suffix']
    query = event['query']
    iterator = event['iterator']
    
    # Optional parameters
    update = event.get('update', False)
    if isinstance(update, str):
        update = update.lower() == 'true'
    
    secret_arn = get_secret_arn()
    put_portal_key_to_env_cmd = f"export PORTAL_KEY=$(aws secretsmanager get-secret-value --region us-west-1 --secret-id {secret_arn} --output text | awk '{{print $4}}' | jq -r .PORTAL_KEY)"
    put_secret_key_to_env_cmd = f"export PORTAL_SECRET_KEY=$(aws secretsmanager get-secret-value --region us-west-1 --secret-id {secret_arn} --output text | awk '{{print $4}}' | jq -r .PORTAL_SECRET_KEY)"
    
    # Prepare the checkfiles command based on update flag
    if update:
        run_checkfiles_cmd = f"venv/bin/python src/checkfiles.py -m prod -q \"{query}\" --update --debug --backend-uri \"{backend_uri}\" --query \"{query}\""
    else:
        run_checkfiles_cmd = f"venv/bin/python src/checkfiles.py -f fastq --debug --backend-uri \"{backend_uri}\" --query \"{query}\""
    
    # Create a combined command that sets up the environment and runs checkfiles
    run_with_debug_cmd = f"""
    #!/bin/bash
    set -x
    set -e

    echo "=== Starting checkfiles execution ==="
    echo "Current directory: $(pwd)"
    echo "Current CHECKFILES_LOG_DIR: $CHECKFILES_LOG_DIR"

    # Check if environment file exists
    if [ ! -f "/home/ubuntu/.env_checkfiles" ]; then
        echo "ERROR: Environment file /home/ubuntu/.env_checkfiles not found"
        echo "=== Directory contents of /home/ubuntu ==="
        ls -la /home/ubuntu/
        echo "=== EC2 instance startup status ==="
        cat /var/log/cloud-init-output.log | tail -n 50 || echo "Cloud-init log not found"
        exit 1
    fi

    # Source environment file
    . /home/ubuntu/.env_checkfiles
    echo "Environment after sourcing:"
    env | grep -E 'CHECKFILES|PYTHON|PATH'

    # Change to checkfiles directory
    cd /home/ubuntu/checkfiles
    echo "Current directory after cd: $(pwd)"

    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "ERROR: Virtual environment not found at $(pwd)/venv"
        echo "=== Directory contents ==="
        ls -la
        echo "=== Setup status ==="
        cat /var/log/cloud-init-output.log | tail -n 50 || echo "Cloud-init log not found"
        exit 1
    fi

    # Verify venv python is available
    if [ ! -f "venv/bin/python" ]; then
        echo "ERROR: Python not found in virtual environment"
        echo "=== Virtual environment contents ==="
        ls -la venv/bin/
        exit 1
    fi
    
    # Activate virtual environment
    . venv/bin/activate
    echo "Python path after activation: $(which python)"
    echo "Python version: $(python --version)"

    # Run the checkfiles command
    echo "=== Running checkfiles command ==="
    CHECKFILES_LOG_DIR="$CHECKFILES_LOG_DIR" python src/checkfiles.py {run_checkfiles_cmd.split('venv/bin/python src/checkfiles.py')[1]}

    # Verify log file
    echo "=== Log File Verification ==="
    echo "CHECKFILES_LOG_DIR: $CHECKFILES_LOG_DIR"
    ls -l $CHECKFILES_LOG_DIR/validation_progress.log || echo "No log file found"
    """
    
    # Execute the command on the instance
    logger.info("Sending SSM command to instance")
    logger.info(f"Command to execute: {run_with_debug_cmd}")
    
    ssm = boto3.client('ssm')
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [run_with_debug_cmd],
            'workingDirectory': ['/home/ubuntu/checkfiles'],
            'executionTimeout': [TWENTY_THREE__HOURS_IN_SECONDS],
        },
        CloudWatchOutputConfig={
            'CloudWatchLogGroupName': 'checkfiles-log',
            'CloudWatchOutputEnabled': True,
        }
    )
    command_id = response['Command']['CommandId']
    logger.info(f"Command sent with ID: {command_id}")

    # Wait for command completion
    time.sleep(2)  # Match upload_report's timing
    
    try:
        result = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id
        )
        logger.info("=== Command Output ===")
        logger.info(f"Status: {result.get('Status')}")
        logger.info(f"Output:\n{result.get('StandardOutputContent', 'No output')}")
        logger.info(f"Error:\n{result.get('StandardErrorContent', 'No error')}")
    except Exception as e:
        logger.error(f"Error getting command output: {e}")
        raise

    # Return execution details
    return {
        'instance_id': instance_id,
        'command_id': command_id,
        'update': update,
        'iterator': iterator,
        'backend_uri': backend_uri,
        'instance_name_suffix': instance_name_suffix,
        'query': query,
        'number_of_files_pending': event.get('number_of_files_pending')
    }
