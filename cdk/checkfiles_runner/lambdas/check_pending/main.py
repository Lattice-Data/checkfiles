import os
import json
import logging
from typing import Dict

import boto3
import requests
from botocore.exceptions import ClientError


logging.basicConfig(
    level=logging.INFO,
    force=True
)


PENDING_FILES_SEARCH = '/search/?type=SequenceAlignmentFile&lab.title=Benjamin+Humphreys%2C+WashU'


def get_secret_arn():
    return os.environ['PORTAL_SECRETS_ARN']


def get_backend_uri():
    return os.environ['BACKEND_URI']


def get_portal_key(secret):
    return secret['PORTAL_KEY']


def get_portal_secret_key(secret):
    return secret['PORTAL_SECRET_KEY']


def get_auth(secret):
    return (get_portal_key(secret), get_portal_secret_key(secret))


def get_secret(secret_arn):
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager'
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_arn
        )
    except ClientError as e:
        raise e
    secret = get_secret_value_response['SecretString']
    logging.info(f'got secret from {secret_arn}')
    return json.loads(secret)


def get_number_of_pending_files(secret: Dict[str, str], backend_uri: str) -> int:
    """
    Get the number of pending files from the backend.
    
    Args:
        secret: Dictionary containing authentication credentials
        backend_uri: Base URI of the backend service
        
    Returns:
        int: Number of pending files
    """
    headers = {'accept': 'application/json'}
    auth = get_auth(secret)
    response = requests.get(
        backend_uri + PENDING_FILES_SEARCH,
        headers=headers,
        auth=auth,
    )
    response.raise_for_status()  # Raises an exception for bad status codes
    data = response.json()
    if 'total' not in data:
        raise ValueError("Unexpected response format: 'total' field missing")
    pending_files = data['total']
    return pending_files


def files_are_pending(pending_files):
    return pending_files > 0


def check_pending_files(event, context):
    backend_uri = get_backend_uri()
    secret_arn = get_secret_arn()
    secret = get_secret(secret_arn)
    logging.info(f'looking for pending files in backend: {backend_uri}')
    number_of_files_pending = get_number_of_pending_files(secret, backend_uri)
    files_pending = files_are_pending(number_of_files_pending)
    if files_pending:
        logging.info(
            f'found {number_of_files_pending} files pending for check in {backend_uri}.')
    else:
        logging.info(f'no files in upload_status pending in {backend_uri}')
    return {
        'files_pending': files_pending,
        'number_of_files_pending': number_of_files_pending,
    }


def validate_environment():
    required_vars = ['PORTAL_SECRETS_ARN', 'BACKEND_URI']
    missing = [var for var in required_vars if var not in os.environ]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
