import json
import boto3
import requests
import logging
import time
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def upload_report_to_slack(event, context):
    """
    Uploads checkfiles validation report to Slack and S3.
    
    This function retrieves the validation report from S3 (uploaded by checkfiles script),
    then uploads it to Slack and moves it to the permanent reports folder in S3.
    
    Args:
        event (dict): Event data containing instance information
        context (object): Lambda context
        
    Returns:
        dict: Status of the upload operation and related metadata
    """
    instance_id = event['instance_id']
    instance_name_suffix = event.get('instance_name_suffix', '')
    
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
        
        # First try to get S3 location from the info file created by validation script
        logging.info(f"Looking for S3 upload info from validation script for instance: {instance_name_suffix}")
        
        try:
            # Try to get s3_upload_info.json from EC2 instance
            ssm = boto3.client('ssm')
            get_info_command = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName='AWS-RunShellScript',
                Parameters={
                    'commands': [
                        '#!/bin/bash',
                        'source /home/ubuntu/.env_checkfiles',
                        'if [ -f "$CHECKFILES_LOG_DIR/s3_upload_info.json" ]; then',
                        '  cat $CHECKFILES_LOG_DIR/s3_upload_info.json',
                        'else',
                        '  echo "INFO_FILE_NOT_FOUND"',
                        'fi'
                    ]
                }
            )
            
            time.sleep(2)
            
            info_result = ssm.get_command_invocation(
                CommandId=get_info_command['Command']['CommandId'],
                InstanceId=instance_id
            )
            
            if info_result['Status'] == 'Success' and 'INFO_FILE_NOT_FOUND' not in info_result['StandardOutputContent']:
                # Parse the S3 upload info
                s3_info = json.loads(info_result['StandardOutputContent'])
                report_s3_key = s3_info['s3_key']
                logging.info(f"Found S3 upload info from validation script: {report_s3_key}")
            else:
                raise Exception("S3 upload info file not found, falling back to file search")
                
        except Exception as e:
            logging.warning(f"Could not get S3 info from validation script: {str(e)}")
            logging.info("Attempting to fetch validation_progress.log directly from EC2 via SSM and upload to S3")

            # Try to have EC2 upload the file directly to S3 to avoid SSM stdout truncation
            try:
                timestamp = time.strftime('%Y%m%d-%H%M%S')
                candidate_s3_key = f"reports/checkfiles-report-{instance_name_suffix}-{timestamp}.tsv"

                ssm = boto3.client('ssm')
                upload_cmd = ssm.send_command(
                    InstanceIds=[instance_id],
                    DocumentName='AWS-RunShellScript',
                    Parameters={
                        'commands': [
                            '#!/bin/bash',
                            'set -e',
                            'source /home/ubuntu/.env_checkfiles || true',
                            'LOG1="${CHECKFILES_LOG_DIR:+$CHECKFILES_LOG_DIR/validation_progress.log}"',
                            'LOG2="/home/ubuntu/checkfiles/validation_progress.log"',
                            'TARGET=""',
                            'if [ -n "$LOG1" ] && [ -f "$LOG1" ]; then TARGET="$LOG1"; fi',
                            'if [ -z "$TARGET" ] && [ -f "$LOG2" ]; then TARGET="$LOG2"; fi',
                            'if [ -z "$TARGET" ]; then echo "MISSING_ALL"; exit 0; fi',
                            f'echo "FOUND:$TARGET"',
                            f'aws s3 cp "$TARGET" "s3://{s3_bucket_name}/{candidate_s3_key}" --content-type "text/tab-separated-values" --metadata "checkfiles-instance={instance_name_suffix},upload-timestamp={timestamp},source-instance-id={instance_id}"'
                        ]
                    }
                )

                time.sleep(3)

                up_res = ssm.get_command_invocation(
                    CommandId=upload_cmd['Command']['CommandId'],
                    InstanceId=instance_id
                )

                stdout = up_res.get('StandardOutputContent', '')
                if up_res['Status'] == 'Success' and 'FOUND:' in stdout:
                    # Verify object exists in S3
                    try:
                        _ = s3.head_object(Bucket=s3_bucket_name, Key=candidate_s3_key)
                        report_s3_key = candidate_s3_key
                        logging.info(f"EC2 uploaded validation log to S3: {report_s3_key}")
                    except Exception:
                        logging.warning("EC2 reported upload success but object not visible yet; will fall back to listing.")
                else:
                    logging.info("EC2 upload path did not succeed or log missing; falling back to S3 listing by prefix")
            except Exception as ec2_upload_e:
                logging.warning(f"EC2-directed S3 upload attempt failed: {ec2_upload_e}")

            # If we still don't have report_s3_key, search S3 by prefix
            if not report_s3_key:
                logging.info("Falling back to searching for report files by pattern")
                prefix = f"reports/checkfiles-report-{instance_name_suffix}-"
                try:
                    response = s3.list_objects_v2(
                        Bucket=s3_bucket_name,
                        Prefix=prefix,
                        MaxKeys=10
                    )
                    if 'Contents' not in response or len(response['Contents']) == 0:
                        raise Exception(f"No validation report files found in S3 with prefix: {prefix}")
                    report_files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
                    latest_report_file = report_files[0]
                    report_s3_key = latest_report_file['Key']
                    logging.info(f"Found validation report file by search: {report_s3_key}")
                except Exception as search_e:
                    raise Exception(f"Error finding validation report file in S3: {str(search_e)}")
        
        # Download the file content from S3
        try:
            response = s3.get_object(Bucket=s3_bucket_name, Key=report_s3_key)
            file_content = response['Body'].read().decode('utf-8')
            
            if not file_content.strip():
                raise Exception("Downloaded report file is empty")
                
            logging.info(f"Successfully downloaded report file from S3: {report_s3_key}")
            
        except Exception as e:
            raise Exception(f"Error downloading report file from S3: {str(e)}")
        
        # Extract filename from S3 key
        filename = report_s3_key.split('/')[-1]  # Get filename from the full S3 key
        
        logging.info(f"File content preview: {file_content[:200]}...")
        
        # File is already in the permanent reports folder in S3 (uploaded by run_checkfiles)
        s3_upload_status = "SUCCESS"  # Already uploaded by run_checkfiles lambda
        logging.info(f"Report already in S3: {s3_bucket_name}/{report_s3_key}")
        
        # Get Slack upload URL
        headers = {
            "Authorization": f"Bearer {slack_token}"
        }

        form_data = {
            "filename": filename,
            "length": len(file_content)
        }

        logging.info(f"Requesting Slack upload URL for file: {filename}")
        upload_url_response = requests.post(
            "https://slack.com/api/files.getUploadURLExternal",
            headers=headers,
            data=form_data
        )
        
        upload_data = upload_url_response.json()
        logging.info(f"Slack upload URL response: {upload_data}")
        
        if not upload_data.get("ok"):
            raise Exception(f"Failed to get Slack upload URL: {upload_data.get('error', 'Unknown error')}")

        upload_url = upload_data["upload_url"]
        file_id = upload_data["file_id"]
        
        # Upload file content to Slack
        upload_response = requests.post(
            upload_url,
            headers={"Content-Type": "text/plain"},
            data=file_content
        )
        
        logging.info(f"Slack file upload response status: {upload_response.status_code}")
        
        if upload_response.status_code != 200:
            raise Exception(f"Slack file upload failed: {upload_response.text}")

        # Complete upload to Slack
        complete_payload = {
            "files": [
                {
                    "id": file_id,
                    "title": filename
                }
            ],
            "channels": slack_channel_id,
            "channel_ids": [slack_channel_id],
            "initial_comment": f"Checkfiles validation report for {instance_name_suffix}"
        }
        
        logging.info("Completing Slack upload...")
        complete_response = requests.post(
            "https://slack.com/api/files.completeUploadExternal",
            headers={
                "Authorization": f"Bearer {slack_token}", 
                "Content-Type": "application/json; charset=utf-8"
            },
            json=complete_payload
        )
        
        response_data = complete_response.json()
        logging.info(f"Slack upload completion response: {response_data}")
        
        if not response_data.get("ok"):
            raise Exception(f"Failed to complete Slack upload: {response_data.get('error', 'Unknown error')}")

        slack_upload_status = "SUCCESS"
        
        # No cleanup needed - file remains in permanent reports folder

        return {
            'status': 'SUCCESS',
            'filename': filename,
            's3_upload_status': s3_upload_status,
            'slack_upload_status': slack_upload_status,
            's3_location': f"s3://{s3_bucket_name}/{report_s3_key}",
            'report_s3_key': report_s3_key,
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