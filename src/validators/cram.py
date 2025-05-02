"""
CRAM file validator using samtools.

This module provides functionality to validate CRAM (Compressed Reference-oriented Alignment Map)
files using the samtools quickcheck command.
"""
import os
import subprocess
import logging
from typing import Dict, Any, IO

logger = logging.getLogger(__name__)

class CramValidator:
    """
    Validator for CRAM files using samtools quickcheck.
    
    This class provides methods to validate CRAM files by utilizing
    the samtools quickcheck command, which performs a quick integrity
    check on the file format.
    """
    
    def __init__(self) -> None:
        """Initialize the CRAM validator."""
        self._check_samtools_availability()
    
    def _check_samtools_availability(self) -> None:
        """
        Check if samtools is available in the system PATH.
        
        Raises:
            RuntimeError: If samtools is not available.
        """
        try:
            result = subprocess.run(
                ["samtools", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False
            )
            if result.returncode != 0:
                logger.warning("samtools command returned non-zero exit code: %d", result.returncode)
        except FileNotFoundError:
            logger.error("samtools not found in PATH. Please install samtools.")
            raise RuntimeError("samtools not found in PATH. Please install samtools.")
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a CRAM file using samtools quickcheck.
        
        Args:
            file_path: Path to the CRAM file to validate.
            
        Returns:
            dict: Validation result containing:
                - valid (bool): Whether the file is valid
                - errors (dict): Any errors encountered
                - warnings (dict): Any warnings generated
                - stats (dict): Statistics about the file
        """
        result = {
            "valid": False,
            "errors": {},
            "warnings": {},
            "stats": {"file_size": 0}
        }
        
        # Check if file exists
        if not os.path.exists(file_path):
            result["errors"]["file_not_found"] = f"File not found: {file_path}"
            return result
        
        # Check if file is empty
        if os.path.getsize(file_path) == 0:
            result["errors"]["empty_file"] = "File is empty"
            return result
        
        # Get file size
        result["stats"]["file_size"] = os.path.getsize(file_path)
        
        # Run samtools quickcheck
        try:
            process = subprocess.run(
                ["samtools", "quickcheck", "-v", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            # quickcheck returns 0 if the file is valid, non-zero otherwise
            if process.returncode == 0:
                result["valid"] = True
            else:
                result["valid"] = False
                result["errors"]["invalid_format"] = process.stderr.strip() or "CRAM file failed validation"
                
        except Exception as e:
            result["errors"]["validation_error"] = f"Error during validation: {str(e)}"
        
        return result
    
    def validate_stream(self, input_stream: IO[bytes], is_gzipped: bool = False) -> Dict[str, Any]:
        """
        Validate a CRAM stream directly using samtools without creating temporary files.
        
        Args:
            input_stream: Binary stream containing CRAM data.
            is_gzipped: Whether the stream contains gzipped data (not used for CRAM)
            
        Returns:
            dict: Validation result containing:
                - valid (bool): Whether the stream is valid
                - errors (dict): Any errors encountered
                - warnings (dict): Any warnings generated
                - stats (dict): Statistics about the stream
        """
        result = {
            "valid": False,
            "errors": {},
            "warnings": {},
            "stats": {"file_size": 0}
        }
        
        # Read the entire content into memory
        # This ensures we can send the full data to samtools in one operation
        try:
            content = input_stream.read()
            total_bytes = len(content)
            result["stats"]["file_size"] = total_bytes
        except Exception as e:
            result["errors"]["stream_error"] = f"Error reading from stream: {str(e)}"
            return result
        
        # Start a samtools process that reads from stdin
        try:
            process = subprocess.Popen(
                ["samtools", "quickcheck", "-v", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Write all data to the process at once
            process.stdin.write(content)
            process.stdin.close()
            
            # Get the output
            stdout, stderr = process.communicate()
            
            # Check return code
            if process.returncode == 0:
                result["valid"] = True
            else:
                result["valid"] = False
                stderr_text = stderr.decode('utf-8', errors='replace').strip()
                result["errors"]["invalid_format"] = stderr_text or "CRAM file failed validation"
                
        except Exception as e:
            result["errors"]["validation_error"] = f"Error during validation: {str(e)}"
            # Try to kill the process if it's still running
            try:
                if 'process' in locals() and process.poll() is None:
                    process.kill()
            except:
                pass
        
        return result
