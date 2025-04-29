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
    
    # First, run a comprehensive diagnostic check focusing on the import issues
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
            "echo '=== Examining helpers module ==='",
            "find /home/ubuntu/checkfiles -path '*/utils/helpers*' -type f | grep -v '__pycache__'",
            "find /usr/local/lib/python* -path '*/utils/helpers*' -type f | grep -v '__pycache__'",
            "echo '=== Checking validation.py imports ==='",
            "grep -n 'import' /home/ubuntu/checkfiles/src/core/validation.py",
            "echo '=== Checking implementation of stream_s3_file ==='",
            "cd /home/ubuntu/checkfiles && source venv/bin/activate && python3 -c \"import sys; print('sys.path:'); print('\\n'.join(sys.path)); print('\\nTrying to find utils.helpers:'); try: import src.utils.helpers; print('src.utils.helpers imported successfully'); print('Available in module:', dir(src.utils.helpers)); except Exception as e: print(f'Error importing src.utils.helpers: {e}');\""
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
    
    # Fix the import path issues
    fix_cmd = ssm.send_command(
        InstanceIds=[event['instance_id']],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [
            "echo '=== FIXING IMPORT PATH ISSUES ==='",
            "cd /home/ubuntu/checkfiles",
            
            # Examine the core validation module to understand the imports
            "echo '=== EXAMINING VALIDATION MODULE ==='",
            "grep -n 'stream_s3_file' /home/ubuntu/checkfiles/src/core/validation.py",
            
            # Check if the utils/helpers directory exists
            "echo '=== CHECKING UTILS STRUCTURE ==='",
            "find /home/ubuntu/checkfiles/src -path '*/utils*' -type d | sort",
            
            # Create the proper module structure if missing
            "mkdir -p /home/ubuntu/checkfiles/src/utils/helpers",
            "touch /home/ubuntu/checkfiles/src/utils/__init__.py",
            "touch /home/ubuntu/checkfiles/src/utils/helpers/__init__.py",
            
            # Create a script to analyze the helpers module
            "cat > /home/ubuntu/checkfiles/analyze_helpers.py << 'EOL'",
            "import importlib.util",
            "import sys",
            "import os",
            "import logging",
            "",
            "# Configure logging",
            "logging.basicConfig(level=logging.INFO)",
            "logger = logging.getLogger(__name__)",
            "",
            "# Try to find the actual stream_s3_file function",
            "def find_stream_s3_file():",
            "    # Check in installed packages",
            "    for path in sys.path:",
            "        for root, dirs, files in os.walk(path):",
            "            for file in files:",
            "                if file.endswith('.py'):",
            "                    full_path = os.path.join(root, file)",
            "                    try:",
            "                        with open(full_path, 'r') as f:",
            "                            content = f.read()",
            "                            if 'def stream_s3_file' in content:",
            "                                logger.info(f'Found potential stream_s3_file in: {full_path}')",
            "                                logger.info('-' * 40)",
            "                                for line in content.splitlines():",
            "                                    if 'def stream_s3_file' in line:",
            "                                        logger.info(f'Function signature: {line}')",
            "                                        break",
            "                    except (UnicodeDecodeError, PermissionError):",
            "                        continue",
            "",
            "# Find actual helpers module content",
            "helpers_paths = []",
            "for path in sys.path:",
            "    helpers_path = os.path.join(path, 'src', 'utils', 'helpers')",
            "    if os.path.exists(helpers_path):",
            "        helpers_paths.append(helpers_path)",
            "",
            "logger.info(f'Found {len(helpers_paths)} potential helpers module locations:')",
            "for path in helpers_paths:",
            "    logger.info(f'- {path}')",
            "",
            "# Try to import the module",
            "try:",
            "    import src.utils.helpers",
            "    logger.info(f'Successfully imported src.utils.helpers: {src.utils.helpers}')",
            "    logger.info(f'Module contents: {dir(src.utils.helpers)}')",
            "except ImportError as e:",
            "    logger.error(f'Failed to import src.utils.helpers: {e}')",
            "",
            "# Call the find function",
            "find_stream_s3_file()",
            "EOL",
            
            # Run the analysis script
            "source venv/bin/activate && python analyze_helpers.py",
            
            # Extract the existing function signature and implementations
            "cat > /home/ubuntu/checkfiles/extract_helpers.py << 'EOL'",
            "import os",
            "import sys",
            "import re",
            "",
            "def search_file_for_function(file_path, function_name):",
            "    try:",
            "        with open(file_path, 'r') as f:",
            "            content = f.read()",
            "            if f'def {function_name}' in content:",
            "                print(f'Found {function_name} in {file_path}')",
            "                # Extract the function definition",
            "                pattern = re.compile(f'def {function_name}.*?\\n(.*?)(?=\\n\\w|$)', re.DOTALL)",
            "                match = pattern.search(content)",
            "                if match:",
            "                    return match.group(0)",
            "    except Exception as e:",
            "        print(f'Error reading {file_path}: {e}')",
            "    return None",
            "",
            "# Search in common locations",
            "search_paths = [",
            "    '/home/ubuntu/checkfiles/src/utils/helpers',",
            "    '/usr/local/lib/python3.10/dist-packages/src/utils/helpers',",
            "]",
            "",
            "functions_found = {}",
            "for base_path in search_paths:",
            "    for root, dirs, files in os.walk(base_path):",
            "        for file in files:",
            "            if file.endswith('.py'):",
            "                filepath = os.path.join(root, file)",
            "                result = search_file_for_function(filepath, 'stream_s3_file')",
            "                if result:",
            "                    functions_found[filepath] = result",
            "",
            "if functions_found:",
            "    for path, func_code in functions_found.items():",
            "        print('='*50)",
            "        print(f'Path: {path}')",
            "        print('-'*50)",
            "        print(func_code)",
            "else:",
            "    print('No stream_s3_file function found')",
            "EOL",
            
            # Run the extraction script
            "source venv/bin/activate && python extract_helpers.py > stream_s3_file_implementations.txt",
            "cat stream_s3_file_implementations.txt",
            
            # Create our utils.helpers module with the correct function
            "cat > /home/ubuntu/checkfiles/src/utils/helpers/__init__.py << 'EOL'",
            "\"\"\"",
            "Helper utilities for file operations and S3 access.",
            "\"\"\"",
            "import os",
            "import io",
            "import boto3",
            "import gzip",
            "from typing import BinaryIO, Dict, List, Any, Optional, Union, Tuple",
            "",
            "def has_gz_extension(filename: str) -> bool:",
            "    \"\"\"",
            "    Check if a filename has a .gz extension.",
            "    ",
            "    Args:",
            "        filename: File name to check",
            "        ",
            "    Returns:",
            "        True if the file has a .gz extension, False otherwise",
            "    \"\"\"",
            "    return filename.endswith('.gz')",
            "",
            "def stream_s3_file(s3_path: str, decompress: bool = False) -> BinaryIO:",
            "    \"\"\"",
            "    Stream a file from S3 as a binary stream.",
            "    ",
            "    Args:",
            "        s3_path: S3 path in the format s3://bucket/key",
            "        decompress: Whether to decompress the stream (for gzipped files)",
            "        ",
            "    Returns:",
            "        Binary IO stream of the file contents",
            "    \"\"\"",
            "    # Parse S3 path",
            "    if not s3_path.startswith('s3://'):",
            "        raise ValueError(f\"Invalid S3 path: {s3_path}. Must start with s3://\")",
            "    ",
            "    parts = s3_path[5:].split('/', 1)  # Remove 's3://' prefix and split on first '/'",
            "    if len(parts) != 2:",
            "        raise ValueError(f\"Invalid S3 path format: {s3_path}. Expected s3://bucket/key\")",
            "    ",
            "    bucket, key = parts",
            "    ",
            "    # Get the object from S3",
            "    s3_client = boto3.client('s3')",
            "    response = s3_client.get_object(Bucket=bucket, Key=key)",
            "    ",
            "    # Read the data into a BytesIO object",
            "    data = response['Body'].read()",
            "    stream = io.BytesIO(data)",
            "    ",
            "    # Decompress if needed",
            "    if decompress:",
            "        # Reset stream position",
            "        stream.seek(0)",
            "        # Create a gzip stream",
            "        gzip_stream = gzip.GzipFile(fileobj=stream, mode='rb')",
            "        # Read all data from gzip stream into a new BytesIO object",
            "        decompressed = io.BytesIO(gzip_stream.read())",
            "        # Reset position and return",
            "        decompressed.seek(0)",
            "        return decompressed",
            "    ",
            "    # Reset stream position and return",
            "    stream.seek(0)",
            "    return stream",
            "EOL",
            
            # Create a test script to verify the implementation
            "cat > /home/ubuntu/checkfiles/test_helpers.py << 'EOL'",
            "from src.utils.helpers import stream_s3_file, has_gz_extension",
            "import sys",
            "",
            "print('PYTHONPATH:', sys.path)",
            "print('Successfully imported helpers module!')",
            "print('has_gz_extension function test:', has_gz_extension('test.gz'))",
            "print('has_gz_extension function test:', has_gz_extension('test.txt'))",
            "print('stream_s3_file function exists:', hasattr(sys.modules['src.utils.helpers'], 'stream_s3_file'))",
            "EOL",
            
            # Run the test script
            "export PYTHONPATH=/home/ubuntu/checkfiles:$PYTHONPATH",
            "source venv/bin/activate && python test_helpers.py",
            
            # Test the validation module imports
            "cat > /home/ubuntu/checkfiles/test_validation_imports.py << 'EOL'",
            "print('Testing imports for validation module...')",
            "try:",
            "    from src.core.validation import stream_s3_file",
            "    print('Successfully imported stream_s3_file from validation!')",
            "except ImportError as e:",
            "    print(f'Error importing from validation: {e}')",
            "",
            "try:",
            "    from src.utils.helpers import stream_s3_file",
            "    print('Successfully imported stream_s3_file from helpers!')",
            "    print('Function signature:', stream_s3_file.__code__.co_varnames)",
            "    print('Function defaults:', stream_s3_file.__defaults__)",
            "except ImportError as e:",
            "    print(f'Error importing from helpers: {e}')",
            "EOL",
            
            "export PYTHONPATH=/home/ubuntu/checkfiles:$PYTHONPATH",
            "source venv/bin/activate && python test_validation_imports.py"
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
    
    # Use a simplified setup command that just ensures PYTHONPATH includes our wrapper
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
