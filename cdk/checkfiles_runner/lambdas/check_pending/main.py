import os
import json
import logging
from typing import Dict, Any, Tuple

import boto3
import requests
from botocore.exceptions import ClientError
from urllib.parse import urljoin


logging.basicConfig(
    level=logging.INFO,
    force=True
)


def get_secret_arn():
    return os.environ['PORTAL_SECRETS_ARN']


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


def build_backend_query_url(backend_uri: str, query: str) -> str:
    """Build a robust search URL from base and query, forcing /search/ path and JSON format."""
    if not backend_uri:
        return query or ''
    query = (query or '').replace('report', 'search')
    # urljoin handles duplicate slashes
    url = urljoin(backend_uri, query)
    # Ensure format=json is present for predictable JSON response
    if 'format=' not in url:
        sep = '&' if '?' in url else '?'
        url = f"{url}{sep}format=json"
    return url


def safe_get_number_of_pending_files(secret: Dict[str, str], backend_query_url: str, timeout_seconds: int = 15) -> Dict[str, Any]:
    """Strict, non-throwing retrieval of pending files count with rich error info."""
    headers = {'accept': 'application/json'}
    auth = get_auth(secret)
    try:
        logging.info(f"GET {backend_query_url}")
        response = requests.get(
            backend_query_url,
            headers=headers,
            auth=auth,
            timeout=timeout_seconds,
        )
        status_code = response.status_code
        if not response.ok:
            # Try to extract JSON error body
            error_body: Dict[str, Any] = {}
            try:
                error_body = response.json()
            except Exception:
                try:
                    text = response.text
                    if text:
                        error_body = {'response_text': text[:4000]}
                except Exception:
                    pass
            return {
                'status': 'error',
                'files_pending': False,
                'number_of_files_pending': 0,
                'error': {
                    'detail': f"HTTP {status_code} for URL: {backend_query_url}",
                    'status_code': status_code,
                    'url': backend_query_url,
                    'response_json': error_body
                }
            }

        # Parse expected JSON
        try:
            data = response.json()
        except Exception as je:
            return {
                'status': 'error',
                'files_pending': False,
                'number_of_files_pending': 0,
                'error': {'detail': f'Invalid JSON response: {je}', 'url': backend_query_url}
            }

        # Prefer 'total'; gracefully fall back to '@total' or len(@graph)
        pending_files = 0
        if isinstance(data, dict):
            if 'total' in data and isinstance(data['total'], int):
                pending_files = data['total']
            elif '@total' in data and isinstance(data['@total'], int):
                pending_files = data['@total']
            elif '@graph' in data and isinstance(data['@graph'], list):
                pending_files = len(data['@graph'])
            else:
                return {
                    'status': 'error',
                    'files_pending': False,
                    'number_of_files_pending': 0,
                    'error': {
                        'detail': "Unexpected response format: missing 'total', '@total', and '@graph'",
                        'url': backend_query_url,
                        'keys': list(data.keys())
                    }
                }
        else:
            return {
                'status': 'error',
                'files_pending': False,
                'number_of_files_pending': 0,
                'error': {'detail': 'Unexpected non-dict JSON response', 'url': backend_query_url}
            }

        return {
            'status': 'ok',
            'files_pending': pending_files > 0,
            'number_of_files_pending': pending_files
        }

    except requests.RequestException as re:
        return {
            'status': 'error',
            'files_pending': False,
            'number_of_files_pending': 0,
            'error': {'detail': f'Request error: {re}', 'url': backend_query_url}
        }


def files_are_pending(pending_files):
    return pending_files > 0


def check_pending_files(event, context):
    query = event.get("query", "")
    backend_uri = event.get('backend_uri', "")

    # Build robust URL and fetch credentials
    backend_uri_query = build_backend_query_url(backend_uri, query)
    secret_arn = get_secret_arn()
    secret = get_secret(secret_arn)

    logging.info(f'looking for pending files in backend: {backend_uri_query}')
    result = safe_get_number_of_pending_files(secret, backend_uri_query, timeout_seconds=15)

    # Strict policy A: never throw; return structured status and error details
    files_pending = result.get('files_pending', False)
    number_of_files_pending = result.get('number_of_files_pending', 0)

    if result.get('status') == 'ok':
        if files_pending:
            logging.info(
                f'found {number_of_files_pending} files pending for check in {backend_uri_query}.')
        else:
            logging.info(f'no files in upload_status pending in {backend_uri_query}')
    else:
        logging.error(f"check_pending_files encountered error: {result.get('error')}")

    response = {
        'files_pending': files_pending,
        'number_of_files_pending': number_of_files_pending,
        'instance_name_suffix': event.get('instance_name_suffix'),
        'backend_uri': backend_uri,
        'query': query,
        'update': event.get('update', False),
        'status': result.get('status', 'error')
    }
    if result.get('status') != 'ok':
        response['error'] = result.get('error')
    return response


def validate_environment():
    required_vars = ['PORTAL_SECRETS_ARN', 'BACKEND_URI']
    missing = [var for var in required_vars if var not in os.environ]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
