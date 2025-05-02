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
    """
    Uploads checkfiles validation report to Slack and S3.
    
    This function retrieves the validation report from an EC2 instance,
    then uploads it to both a Slack channel and an S3 bucket.
    
    Args:
        event (dict): Event data containing instance information
        context (object): Lambda context
        
    Returns:
        dict: Status of the upload operation and related metadata
    """
    instance_id = event['instance_id']
    instance_name_suffix = event.get('instance_name_suffix', '')
    
    ssm = boto3.client('ssm')
    secrets = boto3.client('secretsmanager')
    s3 = boto3.client('s3')
    
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
        
        # Get S3 bucket name from environment
        s3_bucket_name = os.environ['S3_BUCKET_NAME']

        # Get file content from EC2
        copy_command = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [
                    '#!/bin/bash',
                    'echo "=== Upload Report Debug ==="',
                    'source /home/ubuntu/.env_checkfiles',
                    'echo "Current CHECKFILES_LOG_DIR: $CHECKFILES_LOG_DIR"',
                    'echo "Current directory: $(pwd)"',
                    'cd "$CHECKFILES_LOG_DIR" || { echo "Failed to cd to $CHECKFILES_LOG_DIR"; exit 1; }',
                    'echo "=== Log File Check ==="',
                    'ls -l validation_progress.log || echo "No validation_progress.log found"',
                    'if [ ! -f "validation_progress.log" ]; then',
                    '  echo "No validation results available" > validation_progress.log',
                    'fi',
                    'echo "=== File Content ==="',
                    'cat validation_progress.log | base64 -w 0'
                ]
            }
        )
        
        time.sleep(2)
        
        result = ssm.get_command_invocation(
            CommandId=copy_command['Command']['CommandId'],
            InstanceId=instance_id
        )
        print('=== SSM Command Result ===')
        print('Status:', result['Status'])
        print('Standard Output:', result.get('StandardOutputContent', 'No output'))
        print('Standard Error:', result.get('StandardErrorContent', 'No error'))
        
        if result['Status'] != 'Success':
            raise Exception(f"Command failed: {result.get('StandardErrorContent', 'No error message available')}")

        # Process base64 content
        base64_content = result['StandardOutputContent'].strip()
        if not base64_content:
            raise Exception("No log content found")
            
        # Find where the base64 content starts (after "=== File Content ===" line)
        try:
            content_lines = base64_content.split('\n')
            start_idx = -1
            for i, line in enumerate(content_lines):
                if line.strip() == "=== File Content ===":
                    start_idx = i + 1
                    break
            
            if start_idx != -1 and start_idx < len(content_lines):
                # Use only the actual base64 content, not the debug output
                base64_content = content_lines[start_idx].strip()
                
            # Add padding if needed
            padding_needed = len(base64_content) % 4
            if padding_needed:
                base64_content += '=' * (4 - padding_needed)
            
            # Try to decode as UTF-8, but fall back to binary if it fails
            try:
                file_content = base64.b64decode(base64_content).decode('utf-8')
            except UnicodeDecodeError:
                # If we can't decode as UTF-8, use binary mode
                binary_content = base64.b64decode(base64_content)
                file_content = binary_content.decode('utf-8', errors='replace')
                
            timestamp = time.strftime('%Y%m%d-%H%M%S')
            filename = f'checkfiles-report-{instance_name_suffix}-{timestamp}.tsv'
        except Exception as e:
            raise Exception(f"Error processing base64 content: {str(e)}. Content: {base64_content[:100]}")
        
        print('file_content')
        print(file_content)
        print('filename')
        print(filename)
        
        # Upload file to S3
        s3_upload_status = "FAILED"
        try:
            s3.put_object(
                Bucket=s3_bucket_name,
                Key=f"reports/{filename}",
                Body=file_content,
                ContentType="text/tab-separated-values"
            )
            s3_upload_status = "SUCCESS"
            logging.info(f"Successfully uploaded report to S3: {s3_bucket_name}/reports/{filename}")
        except Exception as e:
            logging.error(f"Error uploading to S3: {str(e)}")
            # Continue with Slack upload even if S3 upload fails
        
        # Get Slack upload URL
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

        slack_upload_status = "SUCCESS"

        return {
            'status': 'SUCCESS',
            'filename': filename,
            's3_upload_status': s3_upload_status,
            'slack_upload_status': slack_upload_status,
            's3_location': f"s3://{s3_bucket_name}/reports/{filename}",
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