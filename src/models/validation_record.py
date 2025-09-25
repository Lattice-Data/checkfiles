import json
import logging
from typing import Any, Dict, Optional

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
        # patching outcomes
        self.patched = False
        self.s3_tagged = False
        # exact payload used for a PATCH request (when attempted)
        self.patch_payload: Optional[Dict[str, Any]] = None
        
    def update_info(self, info_dict: Dict[str, Any]) -> None:
        """Update validation information with dictionary of metadata.

        Ensures that specific fields like `read_length` are normalized to the
        expected types (e.g., integers) to avoid downstream type mismatches
        during logging and patching.
        """
        if not info_dict:
            return

        normalized_info: Dict[str, Any] = dict(info_dict)

        # Normalize read_length to an integer if present
        if 'read_length' in normalized_info and normalized_info['read_length'] is not None:
            try:
                value = normalized_info['read_length']
                if not isinstance(value, int):
                    # Convert strings like "100" or "100.0", and floats like 100.0, to int
                    normalized_info['read_length'] = int(float(str(value)))
            except Exception:
                # If conversion fails, leave as-is; validator should ensure correctness
                pass

        self.info.update(normalized_info)
        
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
