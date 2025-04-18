import logging
import time

import boto3

logging.basicConfig(
    level=logging.INFO,
    force=True
)

def get_checkfiles_command_status(event, context):
    command_id = event['command_id']
    instance_id = event['instance_id']
    instance_name_suffix = event.get('instance_name_suffix', '')
    number_of_files_pending = event.get('number_of_files_pending', 0)
    iterator = event.get('iterator', {})
    backend_uri = event.get('backend_uri')
    query = event.get('query')
    update = event.get('update')

    ssm = boto3.client('ssm')
    
    try:
        count_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [
                    # Adjust this path to match your actual log file location
                    'wc -l /home/ubuntu/checkfiles/report.tsv || echo "0"'
                ]
            }
        )
        
        time.sleep(2)
        
        count_result = ssm.get_command_invocation(
            CommandId=count_response['Command']['CommandId'],
            InstanceId=instance_id
        )
        
        try:
            line_count = int(count_result['StandardOutputContent'].split()[0])
        except (ValueError, IndexError):
            line_count = 0
            
        result = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id
        )
        
        status = result['Status']
        
        return {
            'checkfiles_command_status': status,
            'instance_id': instance_id,
            'command_id': command_id,
            'instance_id_list': [instance_id],
            'in_progress': status in ['Pending', 'InProgress'],
            'iterator': iterator,
            'line_count': line_count,
            'number_of_files_pending': number_of_files_pending,
            'instance_name_suffix': instance_name_suffix,
            'backend_uri': backend_uri,
            'query': query,
            'update': update
        }
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        raise e
