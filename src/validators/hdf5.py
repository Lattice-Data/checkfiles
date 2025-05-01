"""
HDF5 file and stream validator.

This module provides validation for HDF5 files to ensure they are properly formatted
and conform to expected standards.
"""

import os
import logging
from typing import Dict, Any, BinaryIO, Optional

from src.validators.base import BaseValidator

# Try to import h5py but handle if it's not available
try:
    import h5py
    H5PY_AVAILABLE = True
except (ImportError, ValueError):
    H5PY_AVAILABLE = False
    logging.warning("h5py module not available. HDF5 validation will be limited.")

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
        self.has_h5py = H5PY_AVAILABLE
        if not self.has_h5py:
            self.logger.warning("h5py not available, HDF5 validation capabilities will be limited")
    
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
        # This method is now redundant as the core logic is handled
        # in core/validation.py which calls validate_stream.
        logger.warning("validate_file is deprecated for Hdf5Validator. Use the validation flow in core/validation.py.")
        
        # Simplified call for basic check
        try:
            # Note: gzipped HDF5 is not standard, assume is_gzipped=False
            with open(file_path, 'rb') as f:
                return self.validate_stream(f, is_gzipped=False)
        except FileNotFoundError:
             return self.format_validation_result(
                valid=False,
                errors={"file_not_found": f"File not found: {file_path}"}
            )
        except Exception as e:
            logger.error(f"Error during basic file validation: {e}")
            return self.format_validation_result(
                valid=False,
                errors={"file_validation_error": str(e)}
            )
    
    def validate_stream(self, input_stream: BinaryIO, is_gzipped: bool = False) -> Dict[str, Any]:
        """
        Validate an HDF5 data stream.
        
        Args:
            input_stream: Binary stream containing HDF5 data
            is_gzipped: Whether the stream contains gzipped data
            
        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the stream data is valid
            - errors (dict): Any validation errors (format specific)
            - warnings (dict): Any validation warnings (format specific)
            - stats (dict): Data statistics (format specific, like group/dataset counts)
        """
        import io
        # import hashlib # No longer needed here
        
        errors = {}
        warnings = {}
        stats = {}
        
        # If h5py is not available, we can't validate the HDF5 structure.
        if not self.has_h5py:
            warnings = {"h5py_missing": "h5py module not available for full validation"}
            
            return self.format_validation_result(
                valid=True,
                warnings=warnings,
                stats=stats
            )
        
        # Hash calculation is now done externally.
        # We attempt to validate the structure directly from the stream.
        # Note: HDF5 might not be fully streamable depending on the file structure
        # and h5py's ability to handle the stream type (seekable vs non-seekable).
        # Gzipped HDF5 is uncommon and not handled here; assume input_stream is raw HDF5 data.
        try:
            try:
                # Try to validate the HDF5 data
                # Attempt to open directly from the stream
                with h5py.File(input_stream, 'r') as f:
                    # Collect basic statistics
                    stats["groups"] = self._count_groups(f)
                    stats["datasets"] = self._count_datasets(f)
                    stats["attributes"] = self._count_attributes(f)
            except Exception as e:
                # This could be due to invalid format or stream incompatibility (e.g., non-seekable)
                errors["validation_error"] = f"Invalid HDF5 structure or stream error: {str(e)}"
                logger.error(f"HDF5 validation failed: {str(e)}")
                # Return immediately on format error, stats might be incomplete/irrelevant
                return self.format_validation_result(valid=False, errors=errors, stats=stats)
            
        except Exception as e:
            errors["validation_error"] = f"Stream validation error: {str(e)}"
            logger.error(f"Stream validation failed: {str(e)}")
            return self.format_validation_result(valid=False, errors=errors)
        
        # Determine if valid (no errors, even if there are warnings)
        valid = len(errors) == 0
        
        return self.format_validation_result(
            valid=valid,
            errors=errors,
            warnings=warnings,
            stats=stats
        )
    
    def _count_groups(self, h5file) -> int:
        """Count the number of groups in an HDF5 file."""
        if not self.has_h5py:
            return 0
            
        count = 0
        
        def visitor_func(name, obj):
            nonlocal count
            if isinstance(obj, h5py.Group):
                count += 1
        
        h5file.visititems(visitor_func)
        return count
    
    def _count_datasets(self, h5file) -> int:
        """Count the number of datasets in an HDF5 file."""
        if not self.has_h5py:
            return 0
            
        count = 0
        
        def visitor_func(name, obj):
            nonlocal count
            if isinstance(obj, h5py.Dataset):
                count += 1
        
        h5file.visititems(visitor_func)
        return count
    
    def _count_attributes(self, h5file) -> int:
        """Count the total number of attributes in an HDF5 file."""
        if not self.has_h5py:
            return 0
            
        count = len(h5file.attrs)
        
        def visitor_func(name, obj):
            nonlocal count
            count += len(obj.attrs)
        
        h5file.visititems(visitor_func)
        return count
