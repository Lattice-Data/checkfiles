"""
HDF5 file and stream validator.

This module provides validation for HDF5 files to ensure they are properly formatted
and conform to expected standards.
"""

import os
import logging
import tempfile
from typing import Dict, Any, BinaryIO, Optional, Tuple, IO
import shutil

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
    
    Note: For H5AD files (a specialized form of HDF5 for single-cell data),
    the H5adValidator should be used instead. Files with 'hdf5' format
    but .h5ad extension will automatically use the H5adValidator.
    """
    
    def __init__(self):
        """Initialize the HDF5 validator."""
        super().__init__()
        self.has_h5py = H5PY_AVAILABLE
        if not self.has_h5py:
            logger.warning("h5py not available, HDF5 validation capabilities will be limited")
    
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
    
    def is_stream_seekable(self, stream: BinaryIO) -> bool:
        """
        Check if a stream is seekable (supports random access).
        
        Args:
            stream: The stream to check
            
        Returns:
            True if the stream is seekable, False otherwise
        """
        return hasattr(stream, 'seek') and hasattr(stream, 'tell')
    
    def create_temp_file_from_stream(self, stream: BinaryIO, is_gzipped: bool = False) -> Tuple[str, IO]:
        """
        Create a temporary file from a stream.
        
        Args:
            stream: The stream to read from
            is_gzipped: Whether the stream contains gzipped data
            
        Returns:
            Tuple containing (temp_file_path, file_object)
        """
        import gzip
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_path = temp_file.name
        
        logger.debug(f"Created temporary file at {temp_path}")
        
        try:
            # Store current position if seekable
            original_pos = None
            if self.is_stream_seekable(stream):
                original_pos = stream.tell()
                stream.seek(0)
            
            # Copy the stream to the temporary file
            # Use larger buffer for better performance
            buffer_size = 1024 * 1024  # 1MB buffer
            
            # If the stream is gzipped but we need raw data
            # (decompression will be handled by h5py)
            if is_gzipped:
                shutil.copyfileobj(stream, temp_file, buffer_size)
            else:
                shutil.copyfileobj(stream, temp_file, buffer_size)
            
            temp_file.flush()
            temp_file.close()
            
            # Restore original position if we changed it and stream is seekable
            if original_pos is not None:
                stream.seek(original_pos)
            
            # Reopen the file in binary read mode
            reopened_file = open(temp_path, 'rb')
            return temp_path, reopened_file
            
        except Exception as e:
            # Clean up on error
            temp_file.close()
            try:
                os.unlink(temp_path)
            except:
                pass
            raise RuntimeError(f"Failed to create temporary file: {str(e)}")
    
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
        errors = {}
        warnings = {}
        stats = {}
        temp_path = None
        temp_file = None
        
        # If h5py is not available, we can't validate the HDF5 structure.
        if not self.has_h5py:
            warnings = {"h5py_missing": "h5py module not available for full validation"}
            
            return self.format_validation_result(
                valid=True,
                warnings=warnings,
                stats=stats
            )
        
        # Check if the stream is seekable
        is_seekable = self.is_stream_seekable(input_stream)
        logger.debug(f"Stream seekable: {is_seekable}")
        
        try:
            # For non-seekable streams (like process.stdout from S3), 
            # we need to create a temporary file
            if not is_seekable:
                logger.debug("Stream is not seekable, creating temporary file")
                temp_path, temp_file = self.create_temp_file_from_stream(input_stream, is_gzipped)
                h5file_input = temp_file
            else:
                # For seekable streams, use directly
                h5file_input = input_stream
                # Make sure we're at the beginning of the stream
                if hasattr(h5file_input, 'seek'):
                    h5file_input.seek(0)
            
            # Try to validate the HDF5 data
            try:
                with h5py.File(h5file_input, 'r') as f:
                    # Collect basic statistics
                    stats["groups"] = self._count_groups(f)
                    stats["datasets"] = self._count_datasets(f)
                    stats["attributes"] = self._count_attributes(f)
            except Exception as e:
                errors["validation_error"] = f"Invalid HDF5 structure or stream error: {str(e)}"
                logger.error(f"HDF5 validation failed: {str(e)}")
                return self.format_validation_result(valid=False, errors=errors, stats=stats)
            
        except Exception as e:
            errors["validation_error"] = f"Stream validation error: {str(e)}"
            logger.error(f"Stream validation failed: {str(e)}")
            return self.format_validation_result(valid=False, errors=errors)
        finally:
            # Clean up temporary file if we created one
            if temp_file:
                try:
                    temp_file.close()
                except:
                    pass
            if temp_path:
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Deleted temporary file {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_path}: {e}")
        
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
