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
    echo '=== Running checkfiles with PYTHONPATH and debug flags ==='
    {setup_env_cmd}
    echo \"PYTHONPATH: $PYTHONPATH\"
    {put_portal_key_to_env_cmd}
    {put_secret_key_to_env_cmd}
    export DEBUG=1
    
    # Debug environment
    echo "=== Environment Debug ==="
    echo "Current CHECKFILES_LOG_DIR: $CHECKFILES_LOG_DIR"
    echo "Current directory: $(pwd)"
    echo "Environment file contents:"
    cat /home/ubuntu/.env_checkfiles || echo "No .env_checkfiles found"
    
    # Use absolute paths for Python
    cd /home/ubuntu/checkfiles
    export PATH=/home/ubuntu/checkfiles/venv/bin:$PATH
    
    # Verify imports are working
    cat > /home/ubuntu/checkfiles/debug_imports.py << 'EOL'
import sys
import os
print('Python sys.path:')
print('\\n'.join(sys.path))
print('\\nEnvironment:')
print(f"CHECKFILES_LOG_DIR: {{os.getenv('CHECKFILES_LOG_DIR')}}")
print('\\nChecking imports:')
try:
    from src.utils.helpers import stream_s3_file, stream_local_file, validate_gzip_format
    print('stream_s3_file, stream_local_file, and validate_gzip_format successfully imported')
except ImportError as e:
    print(f'Error importing helpers: {{e}}')
EOL
    
    # Run the debug script
    /home/ubuntu/checkfiles/venv/bin/python /home/ubuntu/checkfiles/debug_imports.py
    
    # Run the actual checkfiles command
    echo "=== Running checkfiles command ==="
    echo "CHECKFILES_LOG_DIR before command: $CHECKFILES_LOG_DIR"
    CHECKFILES_LOG_DIR="$CHECKFILES_LOG_DIR" /home/ubuntu/checkfiles/venv/bin/python /home/ubuntu/checkfiles/src/checkfiles.py {run_checkfiles_cmd.split('venv/bin/python src/checkfiles.py')[1]}
    echo "=== Checkfiles command completed ==="
    echo "Current directory: $(pwd)"
    echo "Validation log exists: $(ls -l validation_progress.log 2>/dev/null || echo 'No log file')"
    """
    
    # Execute the command on the instance
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
