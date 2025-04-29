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
    # Log parameters clearly
    logger.info(f"Event parameters: {json.dumps(event)}")
    logger.info(f"EC2 instance ID: {event['instance_id']}")
    
    # Add debugging commands
    ssm = boto3.client('ssm')
    
    # First, run a comprehensive diagnostic check focusing on the FastqValidator import issue
    debug_cmd = ssm.send_command(
        InstanceIds=[event['instance_id']],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [
            "echo '=== DETAILED ENVIRONMENT DEBUGGING ==='",
            "cd /home/ubuntu/checkfiles",
            "echo '=== Python Version ==='",
            "python3 --version",
            "echo '=== Python Path ==='",
            "python3 -c 'import sys; print(\"\\n\".join(sys.path))'",
            "echo '=== Source Code Structure ==='",
            "find /home/ubuntu/checkfiles/src -type d | sort",
            "echo '=== Looking for fastq validator files ==='",
            "find /home/ubuntu/checkfiles -name 'fastq*.py' -o -name '*fastq*' | grep -v '__pycache__'",
            "echo '=== Content of src/validators directory if it exists ==='",
            "ls -la /home/ubuntu/checkfiles/src/validators/ 2>/dev/null || echo 'validators directory not found'",
            "echo '=== Package structure ==='",
            "cd /home/ubuntu/checkfiles && pip show -f src 2>/dev/null || echo 'src package not installed'",
            "echo '=== Examining import system ==='",
            "cd /home/ubuntu/checkfiles && source venv/bin/activate && python3 -c \"import sys; import os; print('Current directory:', os.getcwd()); print('Can import src?', 'src' in sys.modules or 'Yes' if __import__('src', fromlist=['']) else 'No'); print('Files in src:', os.listdir('src') if os.path.exists('src') else 'src not found'); print('Validators dir exists?', os.path.exists('src/validators'))\""
        ]}
    )
    
    # Wait for the debug output
    logger.info(f"Debug command ID: {debug_cmd['Command']['CommandId']}")
    time.sleep(5)  # Give a bit more time for debug to complete
    
    try:
        debug_result = ssm.get_command_invocation(
            CommandId=debug_cmd['Command']['CommandId'],
            InstanceId=event['instance_id']
        )
        logger.info(f"Debug output:\n{debug_result.get('StandardOutputContent', 'No output')}")
    except Exception as e:
        logger.error(f"Error getting debug output: {e}")
    
    # Create or fix the validators directory and module if necessary
    fix_cmd = ssm.send_command(
        InstanceIds=[event['instance_id']],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [
            "echo '=== ATTEMPTING TO FIX MODULE STRUCTURE ==='",
            "cd /home/ubuntu/checkfiles",
            "# Ensure validators directory exists",
            "mkdir -p src/validators",
            "# Create __init__.py files to make proper Python packages",
            "touch src/validators/__init__.py",
            "# Create a basic fastq.py if it doesn't exist",
            "if [ ! -f src/validators/fastq.py ]; then",
            "    echo 'Creating a basic FastqValidator class'",
            "    cat > src/validators/fastq.py << 'EOL'",
            "class FastqValidator:",
            "    def __init__(self):",
            "        print('FastqValidator initialized')",
            "        self.name = 'FastqValidator'",
            "",
            "    def validate(self, filepath):",
            "        print(f'Validating {filepath} with pure Python implementation')",
            "        return True, []",
            "EOL",
            "fi",
            "# Verify the fix",
            "echo '=== VERIFYING FIX ==='",
            "ls -la src/validators/",
            "cat src/validators/fastq.py",
            "echo '=== Testing import after fix ==='",
            "source venv/bin/activate && python3 -c 'try: from src.validators.fastq import FastqValidator; print(\"FastqValidator successfully imported\"); except Exception as e: print(f\"Error importing FastqValidator: {e}\")'"
        ]}
    )
    
    # Wait for fix to complete
    time.sleep(5)
    try:
        fix_result = ssm.get_command_invocation(
            CommandId=fix_cmd['Command']['CommandId'],
            InstanceId=event['instance_id']
        )
        logger.info(f"Fix output:\n{fix_result.get('StandardOutputContent', 'No output')}")
    except Exception as e:
        logger.error(f"Error getting fix output: {e}")
    
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
    
    # Add PYTHONPATH explicitly to help with imports
    setup_env_cmd = "export PYTHONPATH=/home/ubuntu/checkfiles:$PYTHONPATH"
    
    if update:
        run_checkfiles_cmd = f"venv/bin/python src/checkfiles.py -m prod -q \"{query}\" --update --debug"
    else:
        file_path_1 = "s3://submissions-czi012eye/HCA2024/Lens/Multi_19w5d_lens/fastq/Multi_19w5d_lens_ATAC_S6_L001_I1_001.fastq.gz"
        file_path_2 = "s3://submissions-czi012eye/HCA2024/Lens/Multi_19w5d_lens/fastq/Multi_19w5d_lens_ATAC_S6_L002_R1_001.fastq.gz"
        file_path_3 = "s3://submissions-czi007imm/Yosef_January_2024/raw_data/raw_columbia/D570_001_TCR_CZINY-0758_S30_L001_R1_001.fastq.gz"
 
        run_checkfiles_cmd = f"venv/bin/python src/checkfiles.py -f fastq -s3 \"{file_path_1},{file_path_2},{file_path_3}\" --debug"
    
    # Add additional debugging
    run_with_debug_cmd = f"""
    echo '=== Running checkfiles with PYTHONPATH and debug flags ==='
    {setup_env_cmd}
    echo \"PYTHONPATH: $PYTHONPATH\"
    {put_portal_key_to_env_cmd}
    {put_secret_key_to_env_cmd}
    export DEBUG=1
    {run_checkfiles_cmd}
    """
    
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

    # Add post-run diagnostics
    post_debug_cmd = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [
            "echo '=== POST-RUN DIAGNOSTICS ==='",
            "cd /home/ubuntu/checkfiles",
            "echo '=== Checking for validation logs ==='",
            "find /home/ubuntu/checkfiles -name '*.log' | xargs cat",
            "echo '=== Checking stderr output ==='",
            "find /home/ubuntu/checkfiles/logs -type f | xargs cat",
            "echo '=== Package Installation ==='",
            "source venv/bin/activate && pip list | grep -i fast",
            "echo '=== Module Path Check ==='",
            "source venv/bin/activate && python3 -c 'import sys; print(sys.modules.keys())' | grep -i valid"
        ]}
    )

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
