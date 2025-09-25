import json
import logging
import requests
from typing import Dict, List, Tuple, Any, Optional

from src.models.validation_record import FileValidationRecord

logger = logging.getLogger(__name__)

def fetch_etag_for_uuid(portal_uri: str, file_uuid: str, auth: Tuple[str, str]) -> Optional[str]:
    """Fetch the current ETag for a file.
    
    Args:
        portal_uri: Base URI for the portal API
        file_uuid: UUID of the file to fetch ETag for
        auth: Tuple of (key_id, secret_key) for authentication
        
    Returns:
        The ETag value or None if not found
    """
    request_uri = f'{portal_uri}/{file_uuid}?frame=edit&datastore=database'
    try:
        response = requests.get(request_uri, auth=auth)
        response.raise_for_status()
        return response.headers.get('etag')
    except requests.RequestException as e:
        logger.error(f"Error fetching ETag for {file_uuid}: {str(e)}")
        return None

def compare_with_db(validation_record: FileValidationRecord, 
                   file_metadata: Dict[str, Any],
                   schema_properties: Dict[str, Any]) -> Dict[str, Any]:
    """Compare validation results with database metadata to determine what needs patching.
    
    Args:
        validation_record: Validation results record
        file_metadata: Current metadata from the database
        schema_properties: Schema properties for the file type
        
    Returns:
        Dictionary with patch payload, consistency messages, and inconsistency messages
    """
    post_json = {}
    metadata_consistency = []
    metadata_inconsistency = []
    
    # Determine allowed keys from schema_properties (payload should only include these)
    allowed_keys = set(schema_properties.keys()) if isinstance(schema_properties, dict) else set()

    # Process key info fields
    for key, results_value in validation_record.info.items():
        # Only consider keys that are part of the schema to avoid sending extraneous fields
        if allowed_keys and key not in allowed_keys:
            # Skip keys not defined in schema
            continue
        # Normalize types for specific keys before comparison/patching
        if key == 'read_length' and results_value is not None:
            try:
                if not isinstance(results_value, int):
                    results_value = int(float(str(results_value)))
            except Exception:
                # If normalization fails, proceed with original value
                pass
        db_value = file_metadata.get(key)
        
        # If field is missing in the database but present in schema, add to patch
        if db_value is None and key in schema_properties:
            post_json[key] = results_value
            logger.info(f"Adding missing field {key}={results_value} to patch")
            
        # If values match, record consistency
        elif results_value == db_value:
            metadata_consistency.append(f'{key} consistent ({results_value})')
            logger.debug(f"{key} consistent between validation and database")
            
        # Handle complex nested objects (like flowcell_details)
        elif isinstance(results_value, list) and isinstance(db_value, list):
            # Handle flowcell_details specifically
            if key == 'flowcell_details' and len(results_value) > 0 and len(db_value) > 0:
                post_flag = True
                # Compare each field in the flowcell details
                for field in ['machine', 'flowcell', 'lane']:
                    if field in results_value[0] and field in db_value[0]:
                        if results_value[0][field] == db_value[0][field]:
                            metadata_consistency.append(
                                f'{key}.{field} consistent ({results_value[0][field]})')
                        else:
                            post_flag = False
                            metadata_inconsistency.append(
                                f'{key}.{field} inconsistent ({results_value[0][field]}-validation, {db_value[0][field]}-db)')
                if post_flag:
                    post_json[key] = results_value
            # Simple list comparison for other list fields
            elif sorted(results_value) == sorted(db_value):
                metadata_consistency.append(f'{key} consistent ({results_value})')
            else:
                metadata_inconsistency.append(
                    f'{key} inconsistent ({results_value}-validation, {db_value}-db)')
                # Only update if the validated list is not empty
                if results_value:
                    post_json[key] = results_value
        else:
            # Record regular inconsistency
            metadata_inconsistency.append(
                f'{key} inconsistent ({results_value}-validation, {db_value}-db)')
            # Add to patch if not already in DB or value is different
            post_json[key] = results_value
    
    # Set validation status to True only when there are no inconsistencies and DB isn't already validated
    if (isinstance(schema_properties, dict) and schema_properties.get('validated')
            and file_metadata.get('validated') is not True
            and not metadata_inconsistency):
        post_json['validated'] = True
        
    return {
        'post_json': post_json,
        'metadata_consistency': metadata_consistency,
        'metadata_inconsistency': metadata_inconsistency
    }

def patch_file(portal_uri: str, auth: Tuple[str, str], validation_record: FileValidationRecord) -> Dict[str, Any]:
    """Patch a file with validation results, ensuring ETag consistency.
    
    Args:
        portal_uri: Base URI for the portal API
        auth: Tuple of (key_id, secret_key) for authentication
        validation_record: Validation record with results to patch
        
    Returns:
        Response JSON from the patch request
    """
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    # Add ETag header if available to prevent concurrent modifications
    if validation_record.original_etag:
        headers['If-Match'] = validation_record.original_etag
    
    payload = validation_record.make_payload()
    logger.info(f'Patching {validation_record.uuid} on {portal_uri}')
    logger.debug(f'Patch payload: {payload}')
    
    try:
        response = requests.patch(
            f'{portal_uri}/{validation_record.uuid}', 
            data=payload, 
            headers=headers, 
            auth=auth
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # Capture rich error details for diagnostics
        error_info: Dict[str, Any] = {"status": "error", "detail": str(e)}
        try:
            resp = getattr(e, 'response', None)
        except Exception:
            resp = None
        if resp is not None:
            try:
                error_info["status_code"] = resp.status_code
            except Exception:
                pass
            try:
                error_info["url"] = resp.url
            except Exception:
                pass
            # Prefer JSON error body if available
            try:
                error_info["response_json"] = resp.json()
            except Exception:
                try:
                    text = resp.text
                    if text:
                        # Truncate to avoid oversized logs
                        error_info["response_text"] = text[:4000]
                except Exception:
                    pass
        logger.error(f"Error patching {validation_record.uuid}: {error_info}")
        return error_info
