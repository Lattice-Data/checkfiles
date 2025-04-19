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
        
        if result['Status'] != 'Success':
            raise Exception(f"Command failed: {result.get('StandardErrorContent', 'No error message available')}")

        # Process base64 content
        base64_content = result['StandardOutputContent'].strip()
        padding_needed = len(base64_content) % 4
        if padding_needed:
            base64_content += '=' * (4 - padding_needed)
        
        file_content = base64.b64decode(base64_content)
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        filename = f'checkfiles-report-{instance_name_suffix}-{timestamp}.tsv.gz'

        # Get upload URL
        headers = {
            "Authorization": f"Bearer {slack_token}"
        }

        form_data = {
            "filename": filename,
            "length": str(len(file_content)),
            "initial_comment": f"Checkfiles report for {instance_name_suffix}",
            "channels": [slack_channel_id]
        }

        upload_url_response = requests.post(
            "https://slack.com/api/files.getUploadURLExternal",
            headers=headers,
            data=form_data
        )

        upload_data = upload_url_response.json()
        if not upload_data.get("ok"):
            raise Exception(f"Failed to get upload URL: {upload_data.get('error', 'Unknown error')}")

        upload_url = upload_data["upload_url"]
        file_id = upload_data["file_id"]

        # Upload file content
        upload_response = requests.post(
            upload_url,
            headers={"Content-Type": "application/octet-stream"},
            data=file_content
        )

        if upload_response.status_code != 200:
            raise Exception(f"File upload failed: {upload_response.text}")

        # Complete upload
        complete_payload = {
            "files": [
                {
                    "id": file_id,
                    "title": filename,
                    "public": True
                }
            ],
            "channel_ids": [slack_channel_id],
            "initial_comment": f"Checkfiles report for {instance_name_suffix}"
        }

        complete_response = requests.post(
            "https://slack.com/api/files.completeUploadExternal",
            headers={
                "Authorization": f"Bearer {slack_token}", 
                "Content-Type": "application/json; charset=utf-8"
            },
            json=complete_payload
        )

        response_data = complete_response.json()
        if not response_data.get("ok"):
            raise Exception(f"Failed to complete upload: {response_data.get('error', 'Unknown error')}")

        # Share file to channel
        if "files" in response_data:
            file_info = response_data["files"][0]
            message_payload = {
                "channel": slack_channel_id,
                "text": f"Checkfiles report for {instance_name_suffix}",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Checkfiles report for {instance_name_suffix}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"<{file_info['url_private_download']}|Download {filename}>"
                        }
                    }
                ]
            }

            share_response = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {slack_token}",
                    "Content-Type": "application/json; charset=utf-8"
                },
                json=message_payload
            )

            if not share_response.json().get("ok"):
                raise Exception(f"Failed to share file: {share_response.text}")

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