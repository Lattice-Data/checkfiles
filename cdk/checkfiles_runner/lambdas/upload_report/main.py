import json
import boto3
import requests
import logging
import time
import os
import tempfile

def upload_report_to_slack(event, context):
    instance_id = event['instance_id']
    instance_name_suffix = event.get('instance_name_suffix', '')
    
    ssm = boto3.client('ssm')
    secrets = boto3.client('secretsmanager')
    
    try:
        # First, check the file status
        check_commands = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [
                    'ls -l /home/ubuntu/checkfiles/',  # List directory contents
                    'pwd',  # Check current directory
                    'whoami',  # Check user context
                    'find /home/ubuntu/checkfiles -name "*.gz"'  # Find any .gz files
                ]
            }
        )
        
        time.sleep(2)
        
        check_result = ssm.get_command_invocation(
            CommandId=check_commands['Command']['CommandId'],
            InstanceId=instance_id
        )
        
        if check_result['Status'] == 'Success':
            logging.info(f"Directory contents: {check_result['StandardOutputContent']}")
        else:
            logging.error(f"Failed to check directory: {check_result['StandardErrorContent']}")

        token_secret = secrets.get_secret_value(
            SecretId=os.environ['SLACK_TOKEN_ARN']
        )['SecretString']
        
        channel_secret = secrets.get_secret_value(
            SecretId=os.environ['SLACK_CHANNEL_ID_ARN']
        )['SecretString']
        
        slack_token = json.loads(token_secret)['BOT_TOKEN']
        slack_channel_id = json.loads(channel_secret)['CHANNEL_ID']
        
        secret = secrets.get_secret_value(
            SecretId=os.environ['PORTAL_SECRETS_ARN']
        )['SecretString']
        
        # Create a temporary file to store the content
        with tempfile.NamedTemporaryFile(suffix='.tsv.gz') as temp_file:
            
            # Use SSM to copy the gzipped file content
            copy_command = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName='AWS-RunShellScript',
                Parameters={
                    'commands': [
                        'cd /home/ubuntu/checkfiles && ' +
                        'if [ ! -f report.tsv.gz ]; then ' +
                        '  echo "File not found in expected location, checking if it needs to be compressed..." && ' +
                        '  if [ -f report.tsv ]; then ' +
                        '    gzip -f report.tsv && ' +
                        '    echo "Compressed report.tsv to report.tsv.gz" ; ' +
                        '  else ' +
                        '    echo "Neither report.tsv nor report.tsv.gz found" ; ' +
                        '    exit 1 ; ' +
                        '  fi ; ' +
                        'fi && ' +
                        'base64 report.tsv.gz'
                    ]
                }
            )
            
            time.sleep(2)  # Wait for command to complete
            
            result = ssm.get_command_invocation(
                CommandId=copy_command['Command']['CommandId'],
                InstanceId=instance_id
            )
            
            if result['Status'] == 'Success':
                import base64
                # Decode base64 content and write to temp file
                file_content = base64.b64decode(result['StandardOutputContent'])
                temp_file.write(file_content)
                temp_file.flush()
                
                # Generate filename with timestamp
                timestamp = time.strftime('%Y%m%d-%H%M%S')
                filename = f'checkfiles-report-{instance_name_suffix}-{timestamp}.tsv.gz'
                
                # Upload to Slack
                with open(temp_file.name, 'rb') as f:
                    files = {
                        'file': (filename, f, 'application/gzip')  # Set correct MIME type for gzipped file
                    }
                    
                    data = {
                        'channels': slack_channel_id,
                        'initial_comment': f'Checkfiles report for {instance_name_suffix}',
                        'title': filename
                    }
                    
                    headers = {
                        'Authorization': f'Bearer {slack_token}'
                    }
                    
                    response = requests.post(
                        'https://slack.com/api/files.upload',
                        headers=headers,
                        data=data,
                        files=files
                    )
                    
                    if response.status_code == 200 and response.json().get('ok'):
                        file_url = response.json().get('file', {}).get('permalink', 'File URL not available')
                        
                        return {
                            'status': 'SUCCESS',
                            'file_url': file_url,
                            'filename': filename,
                            # Preserve other state data
                            'instance_id': instance_id,
                            'instance_id_list': event.get('instance_id_list', []),
                            'instance_name_suffix': instance_name_suffix,
                            'backend_uri': event.get('backend_uri'),
                            'query': event.get('query'),
                            'update': event.get('update')
                        }
                    else:
                        raise Exception(f"Failed to upload to Slack: {response.text}")
            else:
                raise Exception(f"Failed to read report file: {result['StandardErrorContent']}")
                
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        raise e