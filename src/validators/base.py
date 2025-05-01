"""
Base validator class that all specific validators will inherit from.
"""
import logging
import hashlib
import zlib
import io
import gzip
import crcmod.predefined
import subprocess
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
    Uses streaming approach with system commands for content_md5sum calculation.
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
        
        # Initialize content size tracker
        self.content_size = 0
        
        # Set up md5 process that will calculate content_md5sum
        # This uses a pipe to gunzip | md5sum, similar to old_lattice_checkfiles.py
        self.md5_process = subprocess.Popen(
            ["gunzip", "--stdout", "-"],  # gunzip from stdin, output to stdout
            stdin=subprocess.PIPE,         # we'll write to this
            stdout=subprocess.PIPE,        # output of gunzip
            stderr=subprocess.PIPE         # capture any errors
        )
        
        # Set up a second process to calculate md5 from gunzip output
        self.md5sum_process = subprocess.Popen(
            ["md5sum"],
            stdin=self.md5_process.stdout,  # read from gunzip's stdout
            stdout=subprocess.PIPE,         # capture the md5sum output
            stderr=subprocess.PIPE          # capture any errors
        )
        
        # Close stdout in the first process to prevent deadlocks
        # This allows EOF to be sent to md5sum when gunzip is done
        self.md5_process.stdout.close()
        
        # For tracking uncompressed size
        self.decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        
        # For error handling
        self.process_failed = False
    
    def read(self, size=-1):
        """
        Read from stream, update hash calculators, and feed data to gunzip process.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Bytes read from the stream
        """
        data = super().read(size)
        
        if data:
            # Feed data to gunzip process for md5sum
            if not self.process_failed:
                try:
                    # Write to gunzip's stdin in a non-blocking way
                    self.md5_process.stdin.write(data)
                    self.md5_process.stdin.flush()
                except BrokenPipeError:
                    # Gunzip may have crashed or closed the pipe
                    self.process_failed = True
                    logger.error("Broken pipe to gunzip process")
                except Exception as e:
                    self.process_failed = True
                    logger.error(f"Error writing to gunzip: {e}")
            
            # Also track uncompressed size using zlib
            try:
                decompressed = self.decompressor.decompress(data)
                if decompressed:
                    self.content_size += len(decompressed)
            except Exception as e:
                logger.error(f"Error in decompression: {e}")
                
        elif not self.process_failed:
            # End of stream - close stdin to signal end of input
            try:
                self.md5_process.stdin.close()
            except Exception as e:
                logger.error(f"Error closing gunzip stdin: {e}")
                self.process_failed = True
                
            # Try to flush decompressor for accurate content size
            try:
                remaining = self.decompressor.flush()
                if remaining:
                    self.content_size += len(remaining)
            except Exception as e:
                logger.error(f"Error flushing decompressor: {e}")
        
        return data
    
    def get_content_md5sum(self) -> str:
        """
        Get the MD5 hash digest of the decompressed content using piped gunzip | md5sum.
        
        Returns:
            Hexadecimal digest of content MD5
        """
        # If the process failed, return an empty string
        if self.process_failed:
            try:
                error = self.md5_process.stderr.read().decode('utf-8', errors='replace') or \
                        self.md5sum_process.stderr.read().decode('utf-8', errors='replace')
                logger.error(f"Content MD5 calculation failed: {error}")
            except:
                pass
            return ""
            
        try:
            # Wait for the md5sum process to complete
            stdout, stderr = self.md5sum_process.communicate(timeout=10)
            
            # Check if process completed successfully
            if self.md5sum_process.returncode != 0:
                error = stderr.decode('utf-8', errors='replace')
                logger.error(f"md5sum process failed: {error}")
                return ""
                
            # Parse the md5sum output to get just the hash
            # md5sum output format is: "hash  -" (hash followed by two spaces and a dash)
            md5sum_output = stdout.decode('utf-8', errors='replace').strip()
            content_md5 = md5sum_output.split(' ')[0]
            
            return content_md5
            
        except subprocess.TimeoutExpired:
            # Process took too long, kill it and return empty string
            logger.error("Timeout waiting for md5sum to complete")
            self.md5sum_process.kill()
            return ""
        except Exception as e:
            logger.error(f"Error getting content md5: {e}")
            return ""
        finally:
            # Clean up any remaining process resources
            try:
                if hasattr(self, 'md5_process') and self.md5_process:
                    if self.md5_process.poll() is None:  # still running
                        self.md5_process.terminate()
            except:
                pass
            try:
                if hasattr(self, 'md5sum_process') and self.md5sum_process:
                    if self.md5sum_process.poll() is None:  # still running
                        self.md5sum_process.terminate()
            except:
                pass
    
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