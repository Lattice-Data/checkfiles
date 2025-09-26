"""Utilities for S3 operations."""

import logging
import datetime
from typing import Dict

logger = logging.getLogger(__name__)

def set_s3_tags(s3_uri: str, validation_successful: bool) -> Dict[str, str]:
    """Set validation tags on an S3 object.
    
    Tags are set when validation completes successfully on files from Lattice DB.
    
    Args:
        s3_uri: The S3 URI of the file
        validation_successful: Whether validation was successful
        
    Returns:
        Dictionary with status information about the tagging operation
    """
    import boto3
    
    result = {}
    
    try:
        # Parse S3 URI
        bucket_name = s3_uri.split('/')[2]
        file_path = s3_uri.replace(f's3://{bucket_name}/', '')
        
        # Create tag set
        tagging = {
            'TagSet': [
                {
                    'Key': 'validated',
                    'Value': 'true' if validation_successful else 'false'
                },
                {
                    'Key': 'validation_version',
                    'Value': '3.0'  # Version can be defined as a constant
                },
                {
                    'Key': 'validation_date',
                    'Value': datetime.datetime.now().isoformat()
                }
            ]
        }
        
        # Apply tags
        s3client = boto3.client("s3")
        response = s3client.put_object_tagging(Bucket=bucket_name, Key=file_path, Tagging=tagging)
        
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            result['status'] = 'success'
        else:
            result['status'] = f"error:{response['ResponseMetadata']['HTTPStatusCode']}"
            
    except Exception as e:
        result['status'] = f"error:{str(e)}"
        logger.error(f"Error setting S3 tags: {str(e)}")
        
    return result
