"""
Base validator class that all specific validators will inherit from.
"""
import logging
import hashlib
import zlib
import io
import gzip
import crcmod.predefined
from typing import Dict, Any, Optional, BinaryIO, Tuple, List, Callable

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass

class HashCalculatingStream(io.BufferedReader):
    """
    Stream wrapper that calculates multiple hash digests while reading.
    This allows calculating multiple hashes in a single pass.
    """
    
    def __init__(self, stream: BinaryIO, hash_calculators: List[Tuple[str, Callable]]):
        """
        Initialize stream wrapper with hash calculators.
        
        Args:
            stream: The input stream to read from
            hash_calculators: List of tuples containing (name, calculator_object)
                              where calculator_object has an update() method
        """
        self.raw_stream = stream
        self.hash_calculators = hash_calculators
        self.total_bytes = 0
        
        # Only use BufferedReader if the stream isn't already one
        if isinstance(stream, io.BufferedReader):
            self._stream = stream
        else:
            try:
                self._stream = io.BufferedReader(stream)
            except (AttributeError, TypeError):
                # If the stream can't be wrapped (e.g., no readable() method)
                # just use it directly
                self._stream = stream
    
    def read(self, size=-1):
        """
        Read from stream and update all hash calculators.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Bytes read from the stream
        """
        data = self._stream.read(size)
        if data:
            self.total_bytes += len(data)
            for _, calculator in self.hash_calculators:
                calculator.update(data)
        return data
    
    def readline(self, size=-1):
        """
        Read a line from stream and update all hash calculators.
        
        Args:
            size: Maximum number of bytes to read
            
        Returns:
            Line read from the stream
        """
        data = self._stream.readline(size)
        if data:
            self.total_bytes += len(data)
            for _, calculator in self.hash_calculators:
                calculator.update(data)
        return data
    
    def get_hash_digests(self) -> Dict[str, str]:
        """
        Get the hex digests for all hash calculators.
        
        Returns:
            Dictionary mapping hash names to their hexadecimal digest values
        """
        return {name: calculator.hexdigest() for name, calculator in self.hash_calculators}
    
    def get_total_bytes(self) -> int:
        """
        Get the total bytes read.
        
        Returns:
            Total bytes read from the stream
        """
        return self.total_bytes

class GzipHashCalculatingStream(HashCalculatingStream):
    """
    Stream wrapper that calculates hash digests for both compressed and uncompressed content.
    For gzipped files, this calculates both regular file hashes and the content_md5sum hash
    of the decompressed content in a single pass, without storing the entire decompressed file.
    """
    
    def __init__(self, stream: BinaryIO, hash_calculators: List[Tuple[str, Callable]]):
        """
        Initialize gzip stream wrapper with hash calculators.
        
        Args:
            stream: The input stream to read from
            hash_calculators: List of tuples containing (name, calculator_object)
                              where calculator_object has an update() method
        """
        super().__init__(stream, hash_calculators)
        
        # Initialize decompressor for streaming decompression
        self.decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)  # This magic number enables gzip format
        
        # Initialize content MD5 calculator
        self.content_md5_calc = hashlib.md5()
        self.content_size = 0
        
        # Flag to track decompressor state
        self.decompressor_finished = False
    
    def read(self, size=-1):
        """
        Read from stream, update all hash calculators, and decompress for content_md5sum.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Bytes read from the stream
        """
        data = super().read(size)
        
        if data:
            try:
                # Decompress data and update content MD5 hash
                decompressed = self.decompressor.decompress(data)
                if decompressed:
                    self.content_md5_calc.update(decompressed)
                    self.content_size += len(decompressed)
            except Exception as e:
                logger.error(f"Error decompressing data: {e}")
        elif not self.decompressor_finished:
            # End of stream but decompressor may have remaining data
            self._flush_decompressor()
            self.decompressor_finished = True
        
        return data
    
    def _flush_decompressor(self):
        """Process any remaining data in the decompressor."""
        try:
            if hasattr(self.decompressor, 'flush'):
                remaining = self.decompressor.flush()
                if remaining:
                    self.content_md5_calc.update(remaining)
                    self.content_size += len(remaining)
        except Exception as e:
            logger.error(f"Error flushing decompressor: {e}")
    
    def get_content_md5sum(self) -> str:
        """
        Get the MD5 hash digest of the decompressed content.
        
        Returns:
            Hexadecimal digest of content MD5
        """
        # Ensure we've processed any remaining decompressed data
        if not self.decompressor_finished:
            self._flush_decompressor()
            self.decompressor_finished = True
            
        return self.content_md5_calc.hexdigest()
    
    def get_content_size(self) -> int:
        """
        Get the total uncompressed bytes.
        
        Returns:
            Total uncompressed bytes read from the stream
        """
        return self.content_size

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
            - stats (dict): File statistics including hash values
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
            - stats (dict): Data statistics including hash values
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