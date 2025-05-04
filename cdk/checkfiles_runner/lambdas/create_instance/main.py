import os
import logging

import boto3


logging.basicConfig(
    level=logging.INFO,
    force=True
)


def get_ami_id():
    return os.environ['AMI_ID']


def get_instance_name():
    return os.environ['INSTANCE_NAME']


def get_instance_profile_arn():
    return os.environ['INSTANCE_PROFILE_ARN']


def get_security_group():
    return os.environ['SECURITY_GROUP']


def get_checkfiles_tag():
    return os.environ['CHECKFILES_TAG']


def get_instance_type_from_number_of_files_pending(number_of_files_pending: int):
    if number_of_files_pending <= 2:
        return 'c6a.large'
    elif number_of_files_pending <= 4:
        return 'c6a.xlarge'
    elif number_of_files_pending <= 8:
        return 'c6a.2xlarge'
    elif number_of_files_pending <= 16:
        return 'c6a.4xlarge'
    elif number_of_files_pending <= 32:
        return 'c6a.8xlarge'
    elif number_of_files_pending <= 128:
        return 'c6a.12xlarge'
    elif number_of_files_pending <= 512:
        return 'c6a.16xlarge'
    else:
        return 'c6a.24xlarge'


def create_checkfiles_instance(event, context):
    base_instance_name = os.environ.get("INSTANCE_NAME", "default-instance")
    instance_name_suffix = event.get("instance_name_suffix", "")
    number_of_files_pending = event.get('number_of_files_pending')
    iterator = event.get('iterator', {})
    backend_uri = event.get('backend_uri')
    query = event.get('query')
    update = event.get('update')
    instance_name = f"{base_instance_name}-{instance_name_suffix}" if instance_name_suffix else base_instance_name
    ami_id = get_ami_id()
    instance_type = get_instance_type_from_number_of_files_pending(
        number_of_files_pending)
    instance_profile_arn = get_instance_profile_arn()
    security_group = get_security_group()
    tag = get_checkfiles_tag()
    
    # Enhanced installation script that explicitly installs required packages
    user_data = f'''#!/bin/bash
    set -ex  # Enable debugging and exit on error
    
    echo "==== Starting checkfiles runtime setup ===="
    cd /home/ubuntu
    
    # Set up scratch space on the existing boot volume
    echo "==== Setting up scratch space ===="
    mkdir -p /mnt/scratch
    chmod 777 /mnt/scratch
    chown ubuntu:ubuntu /mnt/scratch
    
    # Clone repository with specific tag
    echo "==== Cloning checkfiles repository ===="
    git clone https://github.com/Lattice-Data/checkfiles.git --branch {tag} --single-branch
    cd checkfiles
    
    # Create environment file for Checkfiles
    echo "==== Setting up environment variables ===="
    echo 'export PYTHONPATH=/home/ubuntu/checkfiles:' > /home/ubuntu/.env_checkfiles
    echo 'export CHECKFILES_LOG_DIR=/home/ubuntu/checkfiles' >> /home/ubuntu/.env_checkfiles
    echo 'export SCRATCH_DIR=/mnt/scratch' >> /home/ubuntu/.env_checkfiles
    chmod +x /home/ubuntu/.env_checkfiles
    
    # Set proper permissions
    echo "==== Setting permissions ===="
    cd /home/ubuntu
    chown -R ubuntu:ubuntu checkfiles/
    
    echo "==== Runtime setup complete ===="
    '''

    ec2 = boto3.resource('ec2')

    boot_disk_volume = {
        'DeviceName': '/dev/sda1',
        'Ebs': {
            'DeleteOnTermination': True,
            'Encrypted': False,
            'VolumeSize': 500,
            'VolumeType': 'gp3',
        }
    }

    logging.info(
        f'instance_type: {instance_type} ami_id: {ami_id} checkfiles_tag: {tag}')
    logging.info(f'user_data: \n {user_data}')

    instances = ec2.create_instances(
        MinCount=1,
        MaxCount=1,
        BlockDeviceMappings=[boot_disk_volume],
        InstanceType=instance_type,
        ImageId=ami_id,
        SecurityGroupIds=[security_group],
        IamInstanceProfile={
            'Arn': instance_profile_arn
        },
        UserData=user_data,
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{
                'Key': 'Name',
                'Value': instance_name
            }]
        }]
    )

    instance = instances[0]

    instance.wait_until_running()

    return {
        'instance_id': instance.id,
        'instance_type': instance.instance_type,
        'iterator': iterator,
        'instance_name_suffix': instance_name_suffix,
        'number_of_files_pending': number_of_files_pending,
        'backend_uri': backend_uri,
        'query': query,
        'update': update
    }
