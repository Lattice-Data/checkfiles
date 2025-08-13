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
        run_checkfiles_cmd = f"python3 src/checkfiles.py -m prod -q \"{query}\" --update --debug --backend-uri \"{backend_uri}\" --query \"{query}\""
    else:
        run_checkfiles_cmd = f"python3 src/checkfiles.py --debug --backend-uri \"{backend_uri}\" --query \"{query}\""
    
    # Create a combined command that sets up the environment and runs checkfiles
    run_with_debug_cmd = f"""
    #!/bin/bash
    set -x
    set -e

    echo "=== Starting checkfiles execution ==="
    echo "Current directory: $(pwd)"
    echo "Current CHECKFILES_LOG_DIR: $CHECKFILES_LOG_DIR"
    
    # Check cloud-init logs to see if setup completed
    echo "=== Cloud-init status ==="
    cat /var/log/cloud-init-output.log | tail -n 50 || echo "Cloud-init log not found"

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

    # Set instance name suffix for S3 upload
    export INSTANCE_NAME_SUFFIX="{instance_name_suffix}"
    echo "INSTANCE_NAME_SUFFIX: $INSTANCE_NAME_SUFFIX"

    # Change to checkfiles directory
    cd /home/ubuntu/checkfiles
    echo "Current directory after cd: $(pwd)"
    
    # Check Python version and installed packages
    echo "Python path: $(which python3)"
    echo "Python version: $(python3 --version)"
    
    # Show installed packages in system Python
    echo "=== Installed Python packages ==="
    pip3 list
    
    # Check for specific packages
    echo "=== Checking for required packages ==="
    pip3 show requests || echo "requests package not found"
    pip3 show boto3 || echo "boto3 package not found"

    # Retrieve portal credentials from AWS Secrets Manager
    echo "=== Retrieving portal credentials ==="
    PORTAL_KEY=$(aws secretsmanager get-secret-value --region us-west-1 --secret-id {secret_arn} --output text | awk '{{print $4}}' | jq -r .PORTAL_KEY)
    PORTAL_SECRET_KEY=$(aws secretsmanager get-secret-value --region us-west-1 --secret-id {secret_arn} --output text | awk '{{print $4}}' | jq -r .PORTAL_SECRET_KEY)
    
    if [ -z "$PORTAL_KEY" ] || [ -z "$PORTAL_SECRET_KEY" ]; then
        echo "ERROR: Failed to retrieve portal credentials"
        exit 1
    else
        echo "Portal credentials retrieved successfully"
    fi

    # Run the checkfiles command
    echo "=== Running checkfiles command ==="
    CHECKFILES_LOG_DIR="$CHECKFILES_LOG_DIR" INSTANCE_NAME_SUFFIX="$INSTANCE_NAME_SUFFIX" PORTAL_KEY="$PORTAL_KEY" PORTAL_SECRET_KEY="$PORTAL_SECRET_KEY" python3 src/checkfiles.py {run_checkfiles_cmd.split('python3 src/checkfiles.py')[1]}

    # Verify log file and S3 upload info
    echo "=== Post-execution verification ==="
    echo "CHECKFILES_LOG_DIR: $CHECKFILES_LOG_DIR"
    ls -l $CHECKFILES_LOG_DIR/validation_progress.log || echo "No validation log file found"
    ls -l $CHECKFILES_LOG_DIR/s3_upload_info.json || echo "No S3 upload info file found"
    if [ -f "$CHECKFILES_LOG_DIR/s3_upload_info.json" ]; then
        echo "S3 upload info:"
        cat $CHECKFILES_LOG_DIR/s3_upload_info.json
    fi
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
    time.sleep(2)
    
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

    # S3 upload is now handled by the validation script itself when it completes
    
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


def upload_validation_log_to_s3(instance_id: str, instance_name_suffix: str) -> dict:
    """Upload the validation progress log from EC2 instance to S3.
    
    This function retrieves the validation_progress.log file from the EC2 instance
    and uploads it to S3 for later processing by the upload_report lambda.
    
    Args:
        instance_id: EC2 instance ID where the log file is located
        instance_name_suffix: Suffix for the instance name to create unique filenames
        
    Returns:
        Dictionary with upload status information
    """
    ssm = boto3.client('ssm')
    s3 = boto3.client('s3')
    
    try:
        # Get the validation log file content from EC2 instance
        logger.info(f"Retrieving validation log from EC2 instance {instance_id}")
        
        get_log_command = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [
                    '#!/bin/bash',
                    'set -e',
                    'source /home/ubuntu/.env_checkfiles || true',
                    'if [ -z "$CHECKFILES_LOG_DIR" ]; then echo "MISSING_ENV_CHECKFILES_LOG_DIR"; exit 0; fi',
                    'if [ ! -d "$CHECKFILES_LOG_DIR" ]; then echo "MISSING_LOG_DIR:$CHECKFILES_LOG_DIR"; exit 0; fi',
                    'if [ -f "$CHECKFILES_LOG_DIR/validation_progress.log" ]; then',
                    '  echo "FOUND:$CHECKFILES_LOG_DIR/validation_progress.log"',
                    '  cat "$CHECKFILES_LOG_DIR/validation_progress.log"',
                    'else',
                    '  echo "MISSING_VALIDATION_LOG"',
                    'fi'
                ]
            }
        )
        
        time.sleep(2)
        
        log_result = ssm.get_command_invocation(
            CommandId=get_log_command['Command']['CommandId'],
            InstanceId=instance_id
        )
        
        if log_result['Status'] != 'Success':
            raise Exception(f"Failed to retrieve log file: {log_result.get('StandardErrorContent', 'Unknown error')}")
        
        log_stdout = log_result['StandardOutputContent'] or ''
        if 'MISSING_VALIDATION_LOG' in log_stdout or 'MISSING_LOG_DIR' in log_stdout or 'MISSING_ENV_CHECKFILES_LOG_DIR' in log_stdout:
            raise Exception("Validation log not found on instance at $CHECKFILES_LOG_DIR; not uploading stub.")
        
        # Strip the optional FOUND:path prefix from stdout before upload
        if log_stdout.startswith('FOUND:'):
            newline_index = log_stdout.find('\n')
            log_content = log_stdout[newline_index+1:] if newline_index != -1 else ''
        else:
            log_content = log_stdout
        
        if not log_content.strip():
            raise Exception("Retrieved log file is empty; not uploading.")
        
        logger.info("Retrieved validation log content from EC2 instance (will not upload here; upload handled elsewhere).")
        
        return {
            'status': 'found',
            'message': 'Validation log located on instance',
        }
        
    except Exception as e:
        error_msg = f"Error uploading validation log to S3: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'failed',
            'error': error_msg,
            's3_key': None
        }
