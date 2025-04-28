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
    
    def create_hash_calculating_stream(self, stream: BinaryIO, is_gzipped: bool = False) -> Tuple[HashCalculatingStream, Dict[str, Any]]:
        """
        Create a stream wrapper that calculates hash values while reading.
        
        Args:
            stream: The input stream to read from
            is_gzipped: Whether the stream contains gzipped data
            
        Returns:
            Tuple containing:
            - A HashCalculatingStream wrapper around the input stream
            - A dictionary with metadata about the stream
        """
        # Initialize hash calculators
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        crc32c_func = crcmod.predefined.Crc('crc-32c')
        
        # Create list of hash calculators
        hash_calculators = [
            ('md5sum', md5_hash),
            ('sha256', sha256_hash),
            ('crc32c', crc32c_func)
        ]
        
        # Create hash calculating stream
        hash_stream = HashCalculatingStream(stream, hash_calculators)
        
        # Initialize metadata
        metadata = {}
        
        # If the file is gzipped, calculate content_md5sum
        if is_gzipped:
            metadata['content_md5sum'] = self._calculate_content_md5sum(stream)
        
        return hash_stream, metadata
    
    def _calculate_content_md5sum(self, stream: BinaryIO) -> str:
        """
        Calculate content_md5sum for a gzipped stream.
        
        This function calculates the MD5 of the decompressed content without 
        actually downloading the entire file.
        
        Args:
            stream: Binary stream containing gzipped data
            
        Returns:
            The content_md5sum as a hexadecimal string
        """
        try:
            # Store the current position
            if hasattr(stream, 'tell'):
                try:
                    current_pos = stream.tell()
                except (OSError, IOError):
                    current_pos = None
            else:
                current_pos = None
                
            # If we can seek back to the beginning, do so
            if current_pos is not None and hasattr(stream, 'seek'):
                try:
                    stream.seek(0)
                except (OSError, IOError):
                    # If seeking fails, stream is not seekable
                    logger.warning("Stream is not seekable, cannot calculate content_md5sum")
                    return None
                
            # Create in-memory copy of the stream if needed
            if current_pos is None or not hasattr(stream, 'seek'):
                # Create an in-memory buffer instead of a temporary file
                memory_buffer = io.BytesIO()
                buffer_size = 4096
                
                while True:
                    chunk = stream.read(buffer_size)
                    if not chunk:
                        break
                    memory_buffer.write(chunk)
                
                # Reset the buffer position
                memory_buffer.seek(0)
                content_stream = memory_buffer
            else:
                # Use the original stream
                content_stream = stream
            
            # Calculate MD5 of decompressed content
            md5_hash = hashlib.md5()
            
            # Create a decompressing wrapper
            try:
                with gzip.GzipFile(fileobj=content_stream, mode='rb') as gz:
                    while True:
                        chunk = gz.read(65536)  # 64KB chunks
                        if not chunk:
                            break
                        md5_hash.update(chunk)
            except Exception as e:
                logger.error(f"Error decompressing content: {e}")
                return None
            
            # Restore original position if possible
            if current_pos is not None and hasattr(stream, 'seek'):
                try:
                    stream.seek(current_pos)
                except (OSError, IOError):
                    pass
            
            return md5_hash.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating content_md5sum: {e}")
            return None
    
    def get_hash_values(self, hash_stream: HashCalculatingStream, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Extract hash values and other statistics from a HashCalculatingStream.
        
        Args:
            hash_stream: The HashCalculatingStream to get hash values from
            metadata: Additional metadata to include in stats
            
        Returns:
            Dictionary containing hash values and file size
        """
        stats = {}
        
        # Add file size
        stats['file_size'] = hash_stream.get_total_bytes()
        
        # Add hash digests
        hash_digests = hash_stream.get_hash_digests()
        for hash_name, digest in hash_digests.items():
            if hash_name == 'crc32c':
                # Format crc32c as lowercase hex
                stats[hash_name] = digest.lower()
            else:
                stats[hash_name] = digest
        
        # Add additional metadata if provided
        if metadata:
            stats.update(metadata)
        
        return stats
    
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