import json
import logging

logger = logging.getLogger(__name__)

class FileValidationRecord:
    """Structured container for file validation results and metadata."""
    
    def __init__(self, file_path, uuid=None, original_etag=None):
        self.file_path = file_path
        self.uuid = uuid
        self.original_etag = original_etag
        self.validation_success = None
        self.info = {}
        self.errors = {}
        self.file_not_found = False
        
    def update_info(self, info_dict):
        """Update validation information with dictionary of metadata."""
        if info_dict:
            self.info.update(info_dict)
        
    def update_errors(self, error_dict):
        """Update validation errors with dictionary of error information."""
        if error_dict:
            self.errors.update(error_dict)
            
    def make_payload(self):
        """Create a JSON patch payload from validation results.
        
        Returns:
            str: JSON-encoded payload for patching the backend
        """
        payload = {}
        
        # Add info fields to payload
        if self.info:
            payload.update(self.info)
            
        # Set validation status
        if self.validation_success is not None:
            payload['validated'] = self.validation_success
        
        return json.dumps(payload)
