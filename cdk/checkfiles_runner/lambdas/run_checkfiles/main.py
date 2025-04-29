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
            "echo '=== Detailed import debugging ==='",
            "cd /home/ubuntu/checkfiles && source venv/bin/activate && python3 -c \"import sys; print('sys.path:'); print('\\n'.join(sys.path)); print('\\nAttempting direct imports:'); try: import src.validators; print('src.validators imported successfully'); except Exception as e: print(f'Error importing src.validators: {e}'); try: from src.validators import fastq; print('src.validators.fastq imported successfully'); except Exception as e: print(f'Error importing src.validators.fastq: {e}'); try: from src.validators.fastq.validator import FastqValidator as Validator1; print('FastqValidator from validator.py imported successfully'); except Exception as e: print(f'Error importing from validator.py: {e}'); try: from src.validators.fastq import FastqValidator as Validator2; print('FastqValidator from fastq/__init__.py imported successfully'); except Exception as e: print(f'Error importing from fastq/__init__.py: {e}'); try: from src.validators import FastqValidator as Validator3; print('FastqValidator from validators/__init__.py imported successfully'); except Exception as e: print(f'Error importing from validators/__init__.py: {e}')\""
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
    
    # Fix the import issues by ensuring correct module imports
    fix_cmd = ssm.send_command(
        InstanceIds=[event['instance_id']],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [
            "echo '=== FIXING PYTHON PATH AND IMPORT ISSUES ==='",
            "cd /home/ubuntu/checkfiles",
            
            # Create/Update the .env_checkfiles file to set proper PYTHONPATH
            "echo 'Creating/updating environment file'",
            "cat > /home/ubuntu/.env_checkfiles << 'EOL'",
            "export PYTHONPATH=/home/ubuntu/checkfiles:$PYTHONPATH",
            "EOL",
            
            # Ensure the checkfiles package directory is in the Python path
            "echo 'Fixing the Python path'",
            "source /home/ubuntu/.env_checkfiles",
            
            # Verify the core/validation.py file has the correct imports
            "echo 'Checking core/validation.py'",
            "grep -n 'import.*FastqValidator' src/core/validation.py || echo 'FastqValidator import not found'",
            
            # Create a test script to verify imports work correctly
            "echo 'Creating test script to verify imports'",
            "cat > /home/ubuntu/checkfiles/test_imports.py << 'EOL'",
            "import sys",
            "import os",
            "print('PYTHONPATH:', os.environ.get('PYTHONPATH', 'Not set'))",
            "print('sys.path:', sys.path)",
            "print('Working directory:', os.getcwd())",
            "print('\\nTrying imports:')",
            "try:",
            "    from src.validators.fastq import FastqValidator",
            "    print('Successfully imported FastqValidator from src.validators.fastq')",
            "    validator = FastqValidator()",
            "    print('Created FastqValidator instance:', validator)",
            "    print('Has validate method:', hasattr(validator, 'validate'))",
            "    print('Has validate_stream method:', hasattr(validator, 'validate_stream'))",
            "    if hasattr(validator, 'validate_stream'):",
            "        print('Signature:', validator.validate_stream.__code__.co_varnames)",
            "except Exception as e:",
            "    print(f'Error importing FastqValidator from src.validators.fastq: {e}')",
            "    try:",
            "        # Try adding the current directory to the path",
            "        sys.path.insert(0, os.getcwd())",
            "        from validators.fastq import FastqValidator",
            "        print('Successfully imported FastqValidator from validators.fastq')",
            "        validator = FastqValidator()",
            "        print('Created FastqValidator instance:', validator)",
            "        print('Has validate method:', hasattr(validator, 'validate'))",
            "        print('Has validate_stream method:', hasattr(validator, 'validate_stream'))",
            "        if hasattr(validator, 'validate_stream'):",
            "            print('Signature:', validator.validate_stream.__code__.co_varnames)",
            "    except Exception as e2:",
            "        print(f'Error importing FastqValidator from validators.fastq: {e2}')",
            "EOL",
            
            # Run the test script
            "echo '=== Running import test ==='",
            "source venv/bin/activate && source /home/ubuntu/.env_checkfiles && python /home/ubuntu/checkfiles/test_imports.py",
            
            # Update the validation.py file to ensure correct imports
            "echo 'Updating validation.py import structure'",
            "cat > /tmp/validation_import_fix.py << 'EOL'",
            "import os",
            "import sys",
            "import re",
            "",
            "# Path to the validation.py file",
            "validation_file = '/home/ubuntu/checkfiles/src/core/validation.py'",
            "",
            "# Read the file",
            "with open(validation_file, 'r') as f:",
            "    content = f.read()",
            "",
            "# Fix the FastqValidator import code",
            "import_pattern = r'try:\\s+from src\\.validators\\.fastq import FastqValidator[^\\n]+\\s+except ImportError[^\\n]+\\s+[^\\n]+\\s+[^\\n]+\\s+[^\\n]+\\s+[^\\n]+\\s+from validators\\.fastq import FastqValidator'",
            "fixed_import = '''try:",
            "            # First, try importing with the full path",
            "            from src.validators.fastq import FastqValidator",
            "            logger.debug(\"Successfully imported FastqValidator\")",
            "        except ImportError as e:",
            "            logger.error(f\"Error importing FastqValidator: {e}\")",
            "            # As a fallback, modify sys.path and try alternative import",
            "            try:",
            "                import sys",
            "                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))",
            "                # Add parent directory to path to allow import from validators",
            "                if current_dir not in sys.path:",
            "                    sys.path.insert(0, current_dir)",
            "                from validators.fastq import FastqValidator",
            "                logger.debug(\"Successfully imported FastqValidator using alternative path\")",
            "            except ImportError as e2:",
            "                logger.error(f\"Error importing FastqValidator from alternative path: {e2}\")",
            "                raise ImportError(f\"Error importing FastqValidator from all paths: {e}, {e2}\")'''",
            "",
            "# Use re.sub with re.DOTALL to match across multiple lines",
            "updated_content = re.sub(import_pattern, fixed_import, content, flags=re.DOTALL)",
            "",
            "# Write the updated content back to the file",
            "with open(validation_file, 'w') as f:",
            "    f.write(updated_content)",
            "",
            "print(f\"Updated {validation_file} successfully\")",
            "EOL",
            
            # Run the update script
            "source venv/bin/activate && python /tmp/validation_import_fix.py",
            
            # Test that validation works
            "echo '=== Testing validation function ==='",
            "source venv/bin/activate && source /home/ubuntu/.env_checkfiles && python -c 'from src.core.validation import initialize_validator; validator = initialize_validator(\"fastq\"); print(f\"Validator initialized: {validator}\")'",
            
            # Create a small test to ensure validate_stream works
            "echo 'Testing validate_stream works correctly'",
            "cat > /tmp/test_validate_stream.py << 'EOL'",
            "from src.core.validation import initialize_validator",
            "import io",
            "",
            "# Create a simple FASTQ content",
            "fastq_content = b'''@SEQ_ID",
            "GATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT",
            "+",
            "!''*((((***+))%%%++)(%%%%).1***-+*''))**55CCF>>>>>>CCCCCCC65'''",
            "",
            "# Initialize validator",
            "validator = initialize_validator('fastq')",
            "print(f\"Validator: {validator}\")",
            "",
            "# Test validation with a BytesIO stream",
            "stream = io.BytesIO(fastq_content)",
            "result = validator.validate_stream(stream)",
            "print(f\"Validation result: {result}\")",
            "EOL",
            
            "source venv/bin/activate && source /home/ubuntu/.env_checkfiles && python /tmp/test_validate_stream.py"
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
    setup_env_cmd = "source /home/ubuntu/.env_checkfiles"
    
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
            "find /home/ubuntu/checkfiles -name '*.log' | xargs cat 2>/dev/null || echo 'No log files found'",
            "echo '=== Checking stderr output ==='",
            "find /home/ubuntu/checkfiles/logs -type f 2>/dev/null | xargs cat 2>/dev/null || echo 'No log files found in logs directory'",
            "echo '=== Package Installation ==='",
            "source venv/bin/activate && pip list | grep -i fast",
            "echo '=== Module Path Check ==='",
            "source venv/bin/activate && python3 -c 'import sys; print([m for m in sys.modules.keys() if \"valid\" in m.lower() or \"fastq\" in m.lower()])'"
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
