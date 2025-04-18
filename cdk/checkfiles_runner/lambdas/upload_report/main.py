import json
import boto3
import requests
import logging
import time
import os
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
                    'cd /home/ubuntu/checkfiles && ls -l'
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

        # Get Slack credentials
        token_secret = secrets.get_secret_value(
            SecretId=os.environ['SLACK_TOKEN_ARN']
        )['SecretString']
        
        channel_secret = secrets.get_secret_value(
            SecretId=os.environ['SLACK_CHANNEL_ID_ARN']
        )['SecretString']
        
        slack_token = json.loads(token_secret)['BOT_TOKEN']
        slack_channel_id = json.loads(channel_secret)['CHANNEL_ID']
        
        # Create a temporary file to store the content
        with tempfile.NamedTemporaryFile(suffix='.tsv.gz') as temp_file:
            # Use SSM to copy the gzipped file content
            copy_command = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName='AWS-RunShellScript',
                Parameters={
                    'commands': [
                        'cd /home/ubuntu/checkfiles && ' +
                        # First verify the file exists and its size
                        'ls -l report.tsv.gz || ls -l report.tsv && ' +
                        # If report.tsv exists but not report.tsv.gz, compress it
                        '[ ! -f report.tsv.gz ] && [ -f report.tsv ] && gzip -f report.tsv; ' +
                        # Output the base64 encoded content without wrapping
                        'base64 -w 0 report.tsv.gz'
                    ]
                }
            )
            
            time.sleep(2)  # Wait for command to complete
            
            result = ssm.get_command_invocation(
                CommandId=copy_command['Command']['CommandId'],
                InstanceId=instance_id
            )
            
            if result['Status'] == 'Success':
                # Add debug logging
                logging.info(f"Command output length: {len(result.get('StandardOutputContent', ''))}")
                logging.info(f"Command output last few chars: {result.get('StandardOutputContent', '')[-10:]}")
                
                # Clean the base64 string
                base64_content = result['StandardOutputContent'].strip()
                # Ensure the length is a multiple of 4 by adding padding if needed
                padding_needed = len(base64_content) % 4
                if padding_needed:
                    base64_content += '=' * (4 - padding_needed)
                
                try:
                    import base64
                    # Decode base64 content and write to temp file
                    file_content = base64.b64decode(base64_content)
                    temp_file.write(file_content)
                    temp_file.flush()
                    
                    logging.info(f"Successfully decoded base64 content, size: {len(file_content)} bytes")
                    
                    # Generate filename with timestamp
                    timestamp = time.strftime('%Y%m%d-%H%M%S')
                    filename = f'checkfiles-report-{instance_name_suffix}-{timestamp}.tsv.gz'
                    
                    # Upload to Slack
                    with open(temp_file.name, 'rb') as f:
                        files = {
                            'file': (filename, f, 'application/gzip')
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
                            error_msg = f"Failed to upload to Slack: {response.text}"
                            logging.error(error_msg)
                            raise Exception(error_msg)
                            
                except Exception as decode_error:
                    logging.error(f"Base64 decode error: {str(decode_error)}")
                    logging.error(f"First 100 chars of content: {base64_content[:100]}")
                    raise Exception(f"Failed to decode base64 content: {str(decode_error)}")
            else:
                error_msg = f"Command failed: {result.get('StandardErrorContent', 'No error message available')}"
                logging.error(error_msg)
                raise Exception(error_msg)
                
    except Exception as e:
        logging.error(f"Error in upload_report_to_slack: {str(e)}")
        raise e