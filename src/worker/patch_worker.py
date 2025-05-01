import logging
import os
from typing import Dict, Any, Tuple, Optional

from src.models.validation_record import FileValidationRecord
from src.backend.patch import fetch_etag_for_uuid, patch_file, compare_with_db

logger = logging.getLogger(__name__)

def patching_worker(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Worker function for patching validation results to the backend.
    
    Args:
        job: Dictionary containing:
            - portal_uri: Base URI for the portal API
            - auth: Tuple of (key_id, secret_key) for authentication
            - validation_record: FileValidationRecord with validation results
            - file_metadata: Dictionary with current file metadata
            - schema_properties: Dictionary with schema properties
            - ignore_active_credentials: Whether to ignore upload credential expiration
    
    Returns:
        Response from the patch operation or None if patching is skipped
    """
    portal_uri = job['portal_uri']
    auth = job['auth']
    validation_record = job['validation_record']
    file_metadata = job.get('file_metadata', {})
    schema_properties = job.get('schema_properties', {})
    ignore_active_credentials = job.get('ignore_active_credentials', False)
    
    # Skip if validation failed
    if not validation_record.validation_success:
        logger.info(f'Validation failed for {validation_record.uuid}, skipping patch')
        return None
        
    # Skip if file has errors
    if validation_record.errors:
        logger.info(f'Validation found errors for {validation_record.uuid}, skipping patch')
        return None
    
    # Check upload credentials expiration if needed
    if not ignore_active_credentials:
        try:
            credentials_expired = check_credentials_expired(portal_uri, validation_record.uuid, auth)
            if not credentials_expired:
                logger.info(f'Upload credentials for {validation_record.uuid} not expired yet, skipping patch')
                return None
        except Exception as e:
            logger.error(f'Error checking credentials for {validation_record.uuid}: {str(e)}')
            return None
    
    # Get current ETag
    current_etag = fetch_etag_for_uuid(portal_uri, validation_record.uuid, auth)
    
    # Check if ETag matches original
    if validation_record.original_etag and current_etag != validation_record.original_etag:
        logger.warning(
            f'ETag mismatch for {validation_record.uuid}: '
            f'original={validation_record.original_etag}, current={current_etag}. '
            f'Will not patch.'
        )
        return None
    
    # Compare with DB to determine what needs to be patched
    comparison_result = compare_with_db(validation_record, file_metadata, schema_properties)
    post_json = comparison_result.get('post_json', {})
    
    # If nothing to patch, skip
    if not post_json:
        logger.info(f'No updates needed for {validation_record.uuid}, skipping patch')
        return None
    
    # Log what we're patching
    logger.info(f'Patching {validation_record.uuid} with fields: {list(post_json.keys())}')
    
    # Prepare validation record for patching (only include fields in post_json)
    patch_record = FileValidationRecord(validation_record.file_path, validation_record.uuid, validation_record.original_etag)
    patch_record.validation_success = validation_record.validation_success
    patch_record.update_info(post_json)
    
    # Patch the file
    patch_response = patch_file(portal_uri, auth, patch_record)
    logger.info(f'Patched {validation_record.uuid}: {patch_response}')
    
    return patch_response

def check_credentials_expired(portal_uri: str, file_uuid: str, auth: Tuple[str, str]) -> bool:
    """Check if upload credentials for a file have expired.
    
    Args:
        portal_uri: Base URI for the portal API
        file_uuid: UUID of the file to check
        auth: Tuple of (key_id, secret_key) for authentication
        
    Returns:
        True if credentials have expired, False otherwise
    """
    import requests
    import datetime
    
    logger.info(f'Checking upload credential expiration status for {file_uuid}')
    request_uri = f'{portal_uri}/{file_uuid}/@@upload'
    
    try:
        response = requests.get(request_uri, auth=auth)
        response.raise_for_status()
        
        # Extract expiration time
        upload_credentials = response.json().get('@graph', [{}])[0].get('upload_credentials', {})
        expiration = upload_credentials.get('expiration')
        
        if not expiration:
            logger.warning(f'No expiration found in upload credentials for {file_uuid}')
            return True
            
        # Parse expiration time (portal times are UTC)
        expiration_time = datetime.datetime.fromisoformat(expiration)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Return True if expired
        return expiration_time < now
        
    except Exception as e:
        logger.error(f'Error checking upload credentials for {file_uuid}: {str(e)}')
        # If we can't check, assume expired to be safe
        return True
