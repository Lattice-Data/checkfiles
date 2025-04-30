import json
import os
import boto3
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
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
    
    # Add diagnostic check 
    ssm = boto3.client('ssm')
    
    # Run a basic diagnostic check to ensure environment is ready
    debug_cmd = ssm.send_command(
        InstanceIds=[event['instance_id']],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [
            "echo '=== ENVIRONMENT DIAGNOSTICS ==='",
            "cd /home/ubuntu/checkfiles",
            "echo '=== Python Version ==='",
            "python3 --version",
            "echo '=== Python Path ==='",
            "python3 -c 'import sys; print(\"\\n\".join(sys.path))'"
        ]}
    )
    
    # Wait for the debug output
    logger.info(f"Debug command ID: {debug_cmd['Command']['CommandId']}")
    time.sleep(2)
    
    try:
        debug_result = ssm.get_command_invocation(
            CommandId=debug_cmd['Command']['CommandId'],
            InstanceId=event['instance_id']
        )
        logger.info(f"Debug output:\n{debug_result.get('StandardOutputContent', 'No output')}")
    except Exception as e:
        logger.error(f"Error getting debug output: {e}")
    
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
    
    # Set up PYTHONPATH to find the modules
    setup_env_cmd = "export PYTHONPATH=/home/ubuntu/checkfiles:/home/ubuntu/checkfiles/src:/usr/local/lib/python3.10/dist-packages:/usr/local/lib/python3.10/site-packages:$PYTHONPATH"
    
    # Prepare the checkfiles command based on update flag
    if update:
        run_checkfiles_cmd = f"venv/bin/python src/checkfiles.py -m prod -q \"{query}\" --update --debug --backend-uri \"{backend_uri}\" --query \"{query}\""
    else:
        run_checkfiles_cmd = f"venv/bin/python src/checkfiles.py -f fastq --debug --backend-uri \"{backend_uri}\" --query \"{query}\""
    
    # Create a combined command that sets up the environment and runs checkfiles
    run_with_debug_cmd = f"""
    # Enable error handling and debugging
    set -x
    set -e
    
    echo '=== Starting checkfiles execution ==='
    
    # Initial environment check
    echo "=== Initial Environment ==="
    env | grep -E 'CHECKFILES|PYTHON|PATH'
    echo "Current directory: $(pwd)"
    
    # Load environment variables from .env_checkfiles
    echo "=== Loading environment from .env_checkfiles ==="
    if [ -f /home/ubuntu/.env_checkfiles ]; then
        while read -r line; do
            if [[ "$line" =~ ^export[[:space:]]+([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
                var_name="${{BASH_REMATCH[1]}}"
                var_value="${{BASH_REMATCH[2]}}"
                export "$var_name=$var_value"
                echo "Set $var_name=$var_value"
            fi
        done < /home/ubuntu/.env_checkfiles
    else
        echo "ERROR: .env_checkfiles not found"
        exit 1
    fi
    
    # Verify environment after loading
    echo "=== Environment After Loading ==="
    env | grep -E 'CHECKFILES|PYTHON|PATH'
    
    # Set up Python environment
    echo "=== Setting up Python environment ==="
    cd /home/ubuntu/checkfiles
    export PATH=/home/ubuntu/checkfiles/venv/bin:$PATH
    echo "Python path: $(which python)"
    echo "Python version: $(python --version)"
    
    # Verify virtual environment
    echo "=== Virtual Environment Check ==="
    ls -la /home/ubuntu/checkfiles/venv/bin/python
    ls -la /home/ubuntu/checkfiles/venv/bin/activate
    
    # Run the actual checkfiles command
    echo "=== Running checkfiles command ==="
    echo "CHECKFILES_LOG_DIR before command: $CHECKFILES_LOG_DIR"
    CHECKFILES_LOG_DIR="$CHECKFILES_LOG_DIR" python /home/ubuntu/checkfiles/src/checkfiles.py {run_checkfiles_cmd.split('venv/bin/python src/checkfiles.py')[1]}
    echo "=== Checkfiles command completed ==="
    
    # Verify log file creation
    echo "=== Log File Verification ==="
    echo "Current directory: $(pwd)"
    echo "CHECKFILES_LOG_DIR: $CHECKFILES_LOG_DIR"
    echo "Log file path: $CHECKFILES_LOG_DIR/validation_progress.log"
    echo "Log file exists: $(ls -l $CHECKFILES_LOG_DIR/validation_progress.log 2>/dev/null || echo 'No log file')"
    echo "Log file contents:"
    cat $CHECKFILES_LOG_DIR/validation_progress.log 2>/dev/null || echo "No log file to read"
    echo "=== End of Log File Verification ==="
    """
    
    # Execute the command on the instance
    logger.info("Sending SSM command to instance")
    logger.info(f"Command to execute: {run_with_debug_cmd}")
    
    ssm = boto3.client('ssm')
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [run_with_debug_cmd],
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

    # Wait a bit and get the command output
    time.sleep(5)
    try:
        result = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id
        )
        logger.info(f"Command output:\n{result.get('StandardOutputContent', 'No output')}")
        logger.info(f"Command error:\n{result.get('StandardErrorContent', 'No error')}")
    except Exception as e:
        logger.error(f"Error getting command output: {e}")

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
