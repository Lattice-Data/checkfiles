"""
HDF5 file and stream validator.

This module provides validation for HDF5 files to ensure they are properly formatted
and conform to expected standards.

Note: HDF5 files require random access for validation and cannot be 
directly validated from a stream without creating a temporary file.
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
    
    Important: HDF5 files require random access for validation. When validating from a 
    stream, the data will be written to a temporary file in the scratch directory.
    
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
        import io
        
        # Check stream type and handle specifically
        stream_type = type(stream).__name__
        logger.debug(f"Creating temp file from stream type: {stream_type}")
        
        # Use the /mnt/scratch directory if available, otherwise use system temp directory
        scratch_dir = os.environ.get('SCRATCH_DIR', '/mnt/scratch')
        if not os.path.exists(scratch_dir):
            try:
                os.makedirs(scratch_dir, exist_ok=True)
            except (PermissionError, OSError):
                scratch_dir = tempfile.gettempdir()
                logger.warning(f"Could not create or access scratch directory. Using system temp: {scratch_dir}")
        
        # Create a temporary file in the scratch directory
        prefix = "hdf5_temp_"
        suffix = ".h5ad"  # Always use .h5ad extension for compatibility
        fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=scratch_dir)
        os.close(fd)  # Close the file descriptor
        
        logger.debug(f"Created temporary file at {temp_path}")
        
        try:
            # Different handling based on stream type
            if isinstance(stream, io.BytesIO) or stream_type in ('BytesIO', '_io.BytesIO'):
                logger.debug("Handling BytesIO stream")
                # BytesIO objects need special handling to reset position properly
                try:
                    current_pos = stream.tell()
                    stream.seek(0)
                    logger.debug(f"Reset BytesIO position from {current_pos} to 0")
                except Exception as e:
                    logger.warning(f"Could not reset BytesIO position: {e}")
                
                # Write the BytesIO content directly to the temp file
                with open(temp_path, 'wb') as temp_file:
                    temp_file.write(stream.read())
                    temp_file.flush()
                
                # Try to reset the stream position for the caller
                try:
                    stream.seek(0)
                except Exception as e:
                    logger.warning(f"Could not reset BytesIO position after reading: {e}")
                
            elif isinstance(stream, io.StringIO) or stream_type in ('StringIO', '_io.StringIO'):
                # StringIO needs to be converted to bytes
                logger.debug("Handling StringIO stream")
                try:
                    current_pos = stream.tell()
                    stream.seek(0)
                    logger.debug(f"Reset StringIO position from {current_pos} to 0")
                except Exception as e:
                    logger.warning(f"Could not reset StringIO position: {e}")
                
                # Write the StringIO content as bytes to the temp file
                with open(temp_path, 'wb') as temp_file:
                    temp_file.write(stream.read().encode('utf-8'))
                    temp_file.flush()
                
                # Try to reset the stream position for the caller
                try:
                    stream.seek(0)
                except Exception as e:
                    logger.warning(f"Could not reset StringIO position after reading: {e}")
            else:
                # For other stream types, use the chunked copy approach
                logger.debug(f"Handling generic stream type: {stream_type}")
                # Reset stream position to beginning if possible
                try:
                    if hasattr(stream, 'seek') and hasattr(stream, 'tell'):
                        current_pos = stream.tell()
                        stream.seek(0)
                        logger.debug(f"Reset stream position from {current_pos} to 0")
                except Exception as e:
                    logger.warning(f"Could not reset stream position: {e}")
                
                # Copy the stream to the temporary file using file objects
                with open(temp_path, 'wb') as temp_file:
                    # Use larger buffer for better performance
                    buffer_size = 1024 * 1024  # 1MB buffer
                    
                    # Read and write in chunks to avoid memory issues with large files
                    data = stream.read(buffer_size)
                    while data:
                        temp_file.write(data)
                        data = stream.read(buffer_size)
                    
                    # Ensure all data is written to disk
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                
                # Try to reset the stream position if possible
                try:
                    if hasattr(stream, 'seek'):
                        stream.seek(0)
                        logger.debug("Reset stream position to 0 after reading")
                except Exception as e:
                    logger.warning(f"Could not reset stream position after reading: {e}")
            
            # Reopen the file in binary read mode
            reopened_file = open(temp_path, 'rb')
            return temp_path, reopened_file
            
        except Exception as e:
            # Clean up on error
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception:
                pass
            raise RuntimeError(f"Failed to create temporary file: {str(e)}")
    
    def validate_stream(self, input_stream: BinaryIO, is_gzipped: bool = False) -> Dict[str, Any]:
        """
        Validate an HDF5 data stream.
        
        Important: HDF5 validation requires random access. This method will create
        a temporary file in the scratch directory if the stream is not seekable.
        
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
        is_seekable = False
        try:
            is_seekable = self.is_stream_seekable(input_stream)
            logger.debug(f"Stream seekable: {is_seekable}")
        except Exception as e:
            logger.warning(f"Error checking if stream is seekable: {e}")
            # Continue with assuming it's not seekable
        
        try:
            # For h5py, we always need to use a physical file path
            # Create a temporary file regardless of whether the stream is seekable
            logger.info("Creating temporary file for HDF5 validation")
            
            # Extra check to ensure input_stream is usable
            if input_stream is None:
                raise ValueError("Input stream is None")
            
            # Check if input_stream has necessary methods
            if not hasattr(input_stream, 'read'):
                raise ValueError(f"Input stream lacks required 'read' method: {type(input_stream)}")
            
            # Create temp file for validation
            try:
                temp_path, temp_file = self.create_temp_file_from_stream(input_stream, is_gzipped)
                logger.info(f"Successfully created temporary file at {temp_path}")
            except Exception as e:
                logger.error(f"Failed to create temporary file: {e}")
                return self.format_validation_result(
                    valid=False,
                    errors={"temp_file_error": f"Failed to create temporary file: {str(e)}"}
                )
            
            # Close the file handle since h5py will open it separately
            if temp_file:
                temp_file.close()
            
            # Verify the temp file exists and is accessible
            if not os.path.exists(temp_path):
                error_msg = f"Temporary file {temp_path} does not exist after creation"
                logger.error(error_msg)
                return self.format_validation_result(
                    valid=False,
                    errors={"temp_file_missing": error_msg}
                )
            
            if not os.access(temp_path, os.R_OK):
                error_msg = f"Temporary file {temp_path} is not readable"
                logger.error(error_msg)
                return self.format_validation_result(
                    valid=False,
                    errors={"temp_file_not_readable": error_msg}
                )
            
            # Try to validate the HDF5 data using the physical file path
            try:
                with h5py.File(temp_path, 'r') as f:
                    # Collect basic statistics
                    stats["groups"] = self._count_groups(f)
                    stats["datasets"] = self._count_datasets(f)
                    stats["attributes"] = self._count_attributes(f)
                    logger.info(f"Successfully validated HDF5 file with {stats['groups']} groups, {stats['datasets']} datasets")
            except Exception as e:
                errors["validation_error"] = f"Invalid HDF5 structure: {str(e)}"
                logger.error(f"HDF5 validation failed: {str(e)}")
                return self.format_validation_result(valid=False, errors=errors, stats=stats)
            
        except Exception as e:
            errors["validation_error"] = f"Stream validation error: {str(e)}"
            logger.error(f"Stream validation failed: {str(e)}")
            return self.format_validation_result(valid=False, errors=errors)
        finally:
            # Clean up temporary file if we created one
            if temp_path:
                try:
                    if os.path.exists(temp_path):
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
