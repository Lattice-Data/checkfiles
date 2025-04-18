import json
import boto3
import requests
import logging
import time
import os
import io
import base64

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
        
        # Get file content from EC2
        copy_command = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [
                    'cd /home/ubuntu/checkfiles && ' +
                    'ls -l report.tsv.gz || ls -l report.tsv && ' +
                    '[ ! -f report.tsv.gz ] && [ -f report.tsv ] && gzip -f report.tsv; ' +
                    'base64 -w 0 report.tsv.gz'
                ]
            }
        )
        
        time.sleep(2)
        
        result = ssm.get_command_invocation(
            CommandId=copy_command['Command']['CommandId'],
            InstanceId=instance_id
        )
        
        if result['Status'] == 'Success':
            # Process base64 content
            base64_content = result['StandardOutputContent'].strip()
            padding_needed = len(base64_content) % 4
            if padding_needed:
                base64_content += '=' * (4 - padding_needed)
            
            try:
                # Decode base64 content
                file_content = base64.b64decode(base64_content)
                logging.info(f"Successfully decoded base64 content, size: {len(file_content)} bytes")
                
                # Generate filename
                timestamp = time.strftime('%Y%m%d-%H%M%S')
                filename = f'checkfiles-report-{instance_name_suffix}-{timestamp}.tsv.gz'

                # Create headers for Slack API calls
                headers = {
                    "Authorization": f"Bearer {slack_token}",
                    "Content-Type": "application/json"
                }

                # Step 1: Get external upload URL
                upload_request_payload = {
                    "filename": filename,
                    "length": len(file_content),  # Use length of our file content
                    "channels": [slack_channel_id]
                }

                upload_url_response = requests.post(
                    "https://slack.com/api/files.getUploadURLExternal",
                    headers=headers,
                    data=json.dumps(upload_request_payload)
                )

                upload_data = upload_url_response.json()
                if not upload_data.get("ok"):
                    raise Exception(f"Failed to get upload URL: {upload_data.get('error', 'Unknown error')}")

                upload_url = upload_data["upload_url"]
                file_id = upload_data["file_id"]

                # Step 2: Upload the file content
                upload_response = requests.post(
                    upload_url,
                    headers={"Content-Type": "application/octet-stream"},
                    data=file_content  # Direct use of our file content
                )

                if upload_response.status_code != 200:
                    raise Exception(f"Upload to Slack failed: {upload_response.text}")

                # Step 3: Complete the upload and attach to channel
                complete_payload = {
                    "files": [
                        {
                            "id": file_id,
                            "title": filename
                        }
                    ],
                    "channel_id": slack_channel_id,
                    "initial_comment": f"Checkfiles report for {instance_name_suffix}"
                }

                complete_response = requests.post(
                    "https://slack.com/api/files.completeUploadExternal",
                    headers=headers,
                    data=json.dumps(complete_payload)
                )

                complete_data = complete_response.json()
                if not complete_data.get("ok"):
                    raise Exception(f"Failed to complete upload: {complete_response.text}")

                # Return success response
                return {
                    'status': 'SUCCESS',
                    'file_url': complete_data.get('file', {}).get('url', 'File URL not available'),
                    'filename': filename,
                    # Preserve other state data
                    'instance_id': instance_id,
                    'instance_id_list': event.get('instance_id_list', []),
                    'instance_name_suffix': instance_name_suffix,
                    'backend_uri': event.get('backend_uri'),
                    'query': event.get('query'),
                    'update': event.get('update')
                }

            except Exception as upload_error:
                logging.error(f"Upload error: {str(upload_error)}")
                raise Exception(f"Failed to upload file: {str(upload_error)}")

        else:
            error_msg = f"Command failed: {result.get('StandardErrorContent', 'No error message available')}"
            logging.error(error_msg)
            raise Exception(error_msg)
        
    except Exception as e:
        logging.error(f"Error in upload_report_to_slack: {str(e)}")
        raise e