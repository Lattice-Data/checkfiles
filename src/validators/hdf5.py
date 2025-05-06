"""Validator for generic HDF5 files (.h5, .hdf5)."""

import logging
import os
from typing import Dict, Any, Optional

# Attempt to import h5py, handling potential ImportError
try:
    import h5py
except ImportError:
    h5py = None 
    # Let initialization fail later if h5py is actually needed and missing

from .base import BaseValidator

logger = logging.getLogger(__name__)

class Hdf5Validator(BaseValidator):
    """Validator for generic HDF5 files.
    
    This validator checks if a file is a valid HDF5 container but does not
    enforce any specific internal structure (unlike H5adValidator).
    It supports files with .h5 or .hdf5 extensions.
    """
    
    def __init__(self):
        """Initialize the HDF5 validator."""
        # Check if h5py is available during initialization
        if h5py is None:
            raise ImportError("h5py library is required for Hdf5Validator but is not installed.")
        super().__init__()

    @property
    def supported_extensions(self) -> Dict[str, bool]:
        """Return supported extensions: .h5 and .hdf5 (no compression support)."""
        # Generic HDF5 validation usually doesn't handle external compression well
        return {
            ".h5": False,
            ".hdf5": False,
        }

    def validate_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """Validate a local HDF5 file.
        
        Checks if the file is a valid HDF5 container using h5py.
        
        Args:
            file_path: The path to the local HDF5 file.
            **kwargs: Additional keyword arguments (ignored).
            
        Returns:
            A dictionary containing validation results ('valid', 'errors', 
            'warnings', 'stats').
        """
        # Use standard dictionaries
        stats: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        warnings: Dict[str, str] = {}
        
        try:
            # Basic check: File exists and is readable
            if not os.path.exists(file_path):
                errors["file_access"] = f"File not found or inaccessible: {file_path}"
                # Use the base class static method to format the return dictionary
                return self.format_validation_result(valid=False, errors=errors, warnings=warnings, stats=stats)

            # --- HDF5 Specific Check --- 
            is_valid_hdf5 = h5py.is_hdf5(file_path)
            stats["is_hdf5_file"] = is_valid_hdf5 # Store boolean result in stats
            if not is_valid_hdf5:
                errors["hdf5_format"] = "The file is not a valid HDF5 container."
            else:
                # Optionally, try opening the file for a deeper check
                try:
                    with h5py.File(file_path, 'r') as f:
                        stats["hdf5_can_open"] = True
                        # stats["hdf5_root_objects"] = len(f.keys())
                except Exception as open_error:
                    logger.warning(f"File is HDF5, but failed to open: {open_error}", exc_info=True)
                    warnings["hdf5_open"] = f"File identified as HDF5, but could not be opened: {str(open_error)}"
                    stats["hdf5_can_open"] = False # Update stat even on warning

            # --- Calculate Hashes --- 
            # Use the base class method to calculate standard hashes
            # Assume self.calculate_hashes exists in BaseValidator and returns a dict
            try:
                hash_stats = self.calculate_hashes(file_path)
                stats.update(hash_stats)
            except Exception as hash_error:
                logger.error(f"Error calculating hashes for {file_path}: {hash_error}", exc_info=True)
                warnings["hash_calculation"] = f"Failed to calculate file hashes: {str(hash_error)}"

        except Exception as e:
            logger.error(f"Unexpected error during HDF5 validation for {file_path}: {e}", exc_info=True)
            errors["unexpected_error"] = f"An unexpected error occurred: {str(e)}"

        # Determine overall validity
        is_valid = not errors and stats.get("is_hdf5_file", False)
        
        # Use the base class static method to format the return dictionary
        return self.format_validation_result(valid=is_valid, errors=errors, warnings=warnings, stats=stats) 