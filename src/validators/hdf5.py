"""
HDF5 file and stream validator.

This module provides validation for HDF5 files to ensure they are properly formatted
and conform to expected standards.
"""

import os
import h5py
import logging
from typing import Dict, Any, BinaryIO, Optional

from src.validators.base import BaseValidator

logger = logging.getLogger(__name__)

class Hdf5Validator(BaseValidator):
    """
    Validator for HDF5 format files and streams.
    
    This validator ensures that HDF5 files are properly formatted and 
    can be opened without errors.
    """
    
    def __init__(self):
        """Initialize the HDF5 validator."""
        super().__init__()
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate an HDF5 file.
        
        Args:
            file_path: Path to the HDF5 file to validate
            
        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the file is valid
            - errors (dict): Any validation errors
            - warnings (dict): Any validation warnings
            - stats (dict): File statistics
        """
        if not os.path.exists(file_path):
            return self.format_validation_result(
                valid=False,
                errors={"file_not_found": f"File not found: {file_path}"}
            )
        
        # Check for empty file
        if os.path.getsize(file_path) == 0:
            return self.format_validation_result(
                valid=False,
                errors={"empty_file": "HDF5 file is empty"}
            )
        
        errors = {}
        warnings = {}
        stats = {}
        
        try:
            # Try to open the file with h5py to validate format
            with h5py.File(file_path, 'r') as f:
                # Collect basic statistics
                stats["groups"] = self._count_groups(f)
                stats["datasets"] = self._count_datasets(f)
                stats["attributes"] = self._count_attributes(f)
            
            logger.debug(f"Validated HDF5 file: {file_path}")
            
        except (IOError, OSError) as e:
            errors["validation_error"] = f"Invalid HDF5 file: {str(e)}"
            logger.error(f"Validation failed: {str(e)}")
            return self.format_validation_result(valid=False, errors=errors)
        except Exception as e:
            errors["validation_error"] = f"Validation error: {str(e)}"
            logger.error(f"Validation failed: {str(e)}")
            return self.format_validation_result(valid=False, errors=errors)
        
        # Determine if valid (no errors, even if there are warnings)
        valid = len(errors) == 0
        
        return self.format_validation_result(
            valid=valid,
            errors=errors,
            warnings=warnings,
            stats=stats
        )
    
    def validate_stream(self, input_stream: BinaryIO) -> Dict[str, Any]:
        """
        Validate an HDF5 data stream.
        
        Args:
            input_stream: Binary stream containing HDF5 data
            
        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the stream data is valid
            - errors (dict): Any validation errors
            - warnings (dict): Any validation warnings
            - stats (dict): Data statistics
        """
        # HDF5 files cannot typically be validated from streams without writing to disk
        return self.format_validation_result(
            valid=False,
            errors={"unsupported_operation": "Stream validation is not supported for HDF5 files"}
        )
    
    def _count_groups(self, h5file) -> int:
        """Count the number of groups in an HDF5 file."""
        count = 0
        
        def visitor_func(name, obj):
            nonlocal count
            if isinstance(obj, h5py.Group):
                count += 1
        
        h5file.visititems(visitor_func)
        return count
    
    def _count_datasets(self, h5file) -> int:
        """Count the number of datasets in an HDF5 file."""
        count = 0
        
        def visitor_func(name, obj):
            nonlocal count
            if isinstance(obj, h5py.Dataset):
                count += 1
        
        h5file.visititems(visitor_func)
        return count
    
    def _count_attributes(self, h5file) -> int:
        """Count the total number of attributes in an HDF5 file."""
        count = len(h5file.attrs)
        
        def visitor_func(name, obj):
            nonlocal count
            count += len(obj.attrs)
        
        h5file.visititems(visitor_func)
        return count
