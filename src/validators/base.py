"""
Base validator class that all specific validators will inherit from.
"""
import logging
from typing import Dict, Any, Optional, BinaryIO, Tuple

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass

class BaseValidator:
    """Base class for all file validators."""
    
    def __init__(self):
        """Initialize the base validator."""
        pass
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """Validate a file and return validation results.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the file is valid
            - errors (dict): Any validation errors
            - warnings (dict): Any validation warnings
            - stats (dict): File statistics
        """
        raise NotImplementedError("Subclasses must implement validate_file")
    
    def validate_stream(self, input_stream: BinaryIO) -> Dict[str, Any]:
        """Validate a data stream and return validation results.
        
        Args:
            input_stream: Binary stream to validate
            
        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the stream data is valid
            - errors (dict): Any validation errors
            - warnings (dict): Any validation warnings
            - stats (dict): Data statistics
        """
        raise NotImplementedError("Subclasses must implement validate_stream")
    
    @staticmethod
    def format_validation_result(valid: bool, errors: Optional[Dict] = None, 
                                warnings: Optional[Dict] = None, 
                                stats: Optional[Dict] = None) -> Dict[str, Any]:
        """Format the validation results in a standardized way.
        
        Args:
            valid: Whether the validation passed
            errors: Dictionary of errors
            warnings: Dictionary of warnings
            stats: Dictionary of statistics
            
        Returns:
            Standardized validation result dictionary
        """
        return {
            "valid": valid,
            "errors": errors or {},
            "warnings": warnings or {},
            "stats": stats or {}
        }