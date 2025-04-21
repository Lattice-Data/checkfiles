"""
SeqKit wrapper module for interfacing with the SeqKit command-line tool.
Supports both file-based and streaming operations.
"""
import subprocess
import logging
import os
import tempfile
from typing import Dict, Any, Optional, List, Union, BinaryIO, IO
import threading

logger = logging.getLogger(__name__)

class SeqKitError(Exception):
    """Exception raised for errors in the SeqKit operations."""
    pass


class SeqKitWrapper:
    """Wrapper for the SeqKit command-line tool with streaming support."""
    
    def __init__(self, binary_path: str = "seqkit"):
        """Initialize the SeqKit wrapper.
        
        Args:
            binary_path: Path to the SeqKit executable
        """
        self.binary_path = binary_path
        if not self._is_installed():
            logger.warning("SeqKit is not installed or not in PATH")
    
    def _is_installed(self) -> bool:
        """Check if SeqKit is installed and available in PATH."""
        try:
            # Capture both stdout and stderr
            result = subprocess.run(
                [self.binary_path, "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False  # Don't raise exception on non-zero exit
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def stats(self, file_path: str = None, input_stream: BinaryIO = None) -> Dict[str, Any]:
        """Run seqkit stats on a file or stream and return the results.
        
        Args:
            file_path: Path to the sequence file (optional if input_stream provided)
            input_stream: Binary input stream (optional if file_path provided)
            
        Returns:
            Dictionary containing stats information
            
        Raises:
            SeqKitError: If SeqKit fails to run or is not installed
            ValueError: If neither file_path nor input_stream is provided
        """
        if not self._is_installed():
            raise SeqKitError("SeqKit is not installed or not in PATH")
        
        if not file_path and not input_stream:
            raise ValueError("Either file_path or input_stream must be provided")
        
        try:
            if file_path:
                # File-based approach
                cmd = [self.binary_path, "stats", file_path]
                output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
            else:
                # Streaming approach
                process = subprocess.Popen(
                    [self.binary_path, "stats"],
                    stdin=input_stream,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    raise SeqKitError(f"SeqKit failed: {stderr}")
                
                output = stdout
            
            # Parse the stats output
            result = {}
            lines = output.strip().split('\n')
            
            if len(lines) >= 2:
                headers = lines[0].split()
                values = lines[1].split()
                
                for i, header in enumerate(headers):
                    if i < len(values):
                        # Convert numeric values
                        try:
                            if '.' in values[i]:
                                result[header] = float(values[i])
                            else:
                                result[header] = int(values[i])
                        except ValueError:
                            result[header] = values[i]
            
            return result
            
        except subprocess.CalledProcessError as e:
            error_msg = e.output if hasattr(e, 'output') else str(e)
            logger.error(f"SeqKit error: {error_msg}")
            raise SeqKitError(f"SeqKit failed: {error_msg}")
    
    def head(self, file_path: str = None, input_stream: BinaryIO = None, num_records: int = 10) -> str:
        """Get the first N records from a sequence file or stream.
        
        Args:
            file_path: Path to the sequence file (optional if input_stream provided)
            input_stream: Binary input stream (optional if file_path provided)
            num_records: Number of records to retrieve
            
        Returns:
            String containing the first N records
            
        Raises:
            SeqKitError: If SeqKit fails to run or is not installed
            ValueError: If neither file_path nor input_stream is provided
        """
        if not self._is_installed():
            raise SeqKitError("SeqKit is not installed or not in PATH")
        
        if not file_path and not input_stream:
            raise ValueError("Either file_path or input_stream must be provided")
        
        try:
            if file_path:
                # File-based approach
                cmd = [self.binary_path, "head", "-n", str(num_records), file_path]
                output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
            else:
                # Streaming approach
                process = subprocess.Popen(
                    [self.binary_path, "head", "-n", str(num_records)],
                    stdin=input_stream,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    raise SeqKitError(f"SeqKit failed: {stderr}")
                
                output = stdout
                
            return output
            
        except subprocess.CalledProcessError as e:
            error_msg = e.output if hasattr(e, 'output') else str(e)
            logger.error(f"SeqKit error: {error_msg}")
            raise SeqKitError(f"SeqKit failed: {error_msg}")
            
    def validate_fastq_streaming(self, input_stream: BinaryIO) -> Dict[str, Any]:
        """Validate a FASTQ input stream and collect stats.
        
        This is a dedicated method for FASTQ validation that works with streams.
        
        Args:
            input_stream: Binary input stream of FASTQ data
            
        Returns:
            Dictionary with validation results and stats
            
        Raises:
            SeqKitError: If validation fails or SeqKit is not available
        """
        # Create a temporary named pipe
        with tempfile.TemporaryDirectory() as temp_dir:
            fifo_path = os.path.join(temp_dir, "fastq_stream")
            os.mkfifo(fifo_path)
            
            # Start a process to write the stream to the pipe
            with open(fifo_path, 'wb') as fifo:
                # Copy data from input_stream to fifo in a separate thread
                import threading
                def copy_stream():
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while True:
                        chunk = input_stream.read(chunk_size)
                        if not chunk:
                            break
                        fifo.write(chunk)
                
                thread = threading.Thread(target=copy_stream)
                thread.start()
                
                # Now process with SeqKit
                try:
                    # First check format validity by examining the first few records
                    self.head(file_path=fifo_path, num_records=5)
                    
                    # If we get here, format is valid, get statistics
                    stats = self.stats(file_path=fifo_path)
                    
                    thread.join()
                    return {
                        "valid": True,
                        "stats": stats
                    }
                except SeqKitError as e:
                    thread.join()
                    return {
                        "valid": False,
                        "error": str(e)
                    }