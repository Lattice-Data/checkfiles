import json
import boto3
import requests
import logging
import time
import os
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
                    '#!/bin/bash',
                    '. /etc/profile.d/checkfiles.sh',
                    'echo "CHECKFILES_LOG_DIR is set to: $CHECKFILES_LOG_DIR"',
                    'cd "$CHECKFILES_LOG_DIR" || { echo "Failed to cd to $CHECKFILES_LOG_DIR"; exit 1; }',
                    'if [ ! -f "validation_progress.log" ]; then',
                    '  echo "No validation results available" > validation_progress.log',
                    'fi',
                    'cat validation_progress.log | base64 -w 0'  # Use cat to ensure proper input to base64
                ]
            }
        )
        
        time.sleep(2)
        
        result = ssm.get_command_invocation(
            CommandId=copy_command['Command']['CommandId'],
            InstanceId=instance_id
        )
        print('result')
        print(result)
        if result['Status'] != 'Success':
            raise Exception(f"Command failed: {result.get('StandardErrorContent', 'No error message available')}")

        # Process base64 content
        base64_content = result['StandardOutputContent'].strip()
        padding_needed = len(base64_content) % 4
        if padding_needed:
            base64_content += '=' * (4 - padding_needed)
        
        file_content = base64.b64decode(base64_content).decode('utf-8')
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        filename = f'checkfiles-report-{instance_name_suffix}-{timestamp}.tsv'
        print('file_content')
        print(file_content)
        print('filename')
        print(filename)
        # Get upload URL
        headers = {
            "Authorization": f"Bearer {slack_token}"
        }

        form_data = {
            "filename": filename,
            "length": len(file_content)
        }

        print('form_data')
        print(form_data)
        upload_url_response = requests.post(
            "https://slack.com/api/files.getUploadURLExternal",
            headers=headers,
            data=form_data
        )
        print('upload_url_response')
        print(upload_url_response.json())

        upload_data = upload_url_response.json()
        if not upload_data.get("ok"):
            raise Exception(f"Failed to get upload URL: {upload_data.get('error', 'Unknown error')}")

        upload_url = upload_data["upload_url"]
        file_id = upload_data["file_id"]
        print(upload_url)
        print(file_id)
        # Upload file content
        upload_response = requests.post(
            upload_url,
            headers={"Content-Type": "text/plain"},
            data=file_content
        )
        print('upload_response')
        print(upload_response)

        if upload_response.status_code != 200:
            raise Exception(f"File upload failed: {upload_response.text}")

        # Complete upload
        complete_payload = {
            "files": [
                {
                    "id": file_id,
                    "title": filename
                }
            ],
            "channels": slack_channel_id,
            "channel_ids": [slack_channel_id],
            "initial_comment": f"Checkfiles report for {instance_name_suffix}"
        }
        print("complete_payload")
        print(complete_payload)

        complete_response = requests.post(
            "https://slack.com/api/files.completeUploadExternal",
            headers={
                "Authorization": f"Bearer {slack_token}", 
                "Content-Type": "application/json; charset=utf-8"
            },
            json=complete_payload
        )
        print("complete_response")
        print(complete_response)

        response_data = complete_response.json()
        if not response_data.get("ok"):
            raise Exception(f"Failed to complete upload: {response_data.get('error', 'Unknown error')}")


        return {
            'status': 'SUCCESS',
            'filename': filename,
            # Preserve other state data
            'instance_id': instance_id,
            'instance_id_list': event.get('instance_id_list', []),
            'instance_name_suffix': instance_name_suffix,
            'backend_uri': event.get('backend_uri'),
            'query': event.get('query'),
            'update': event.get('update')
        }

    except Exception as e:
        logging.error(f"Error in upload_report_to_slack: {str(e)}")
        raise e