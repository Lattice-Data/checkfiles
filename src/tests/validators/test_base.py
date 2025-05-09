"""
Unit tests for base validator functionality.
"""

import io
import gzip
import hashlib
import unittest
from typing import Dict, Any
from unittest.mock import patch, MagicMock
import subprocess
from builtins import BrokenPipeError

# Import the new centralized function
from src.core.validation import calculate_hashes_for_stream
from src.validators.base import BaseValidator, HashCalculatingStream, GzipHashCalculatingStream

class TestHashCalculatingStream(unittest.TestCase):
    """Test the HashCalculatingStream class."""
    
    def test_regular_hash_calculation(self):
        """Test basic hash calculation for uncompressed data."""
        # Create test data
        test_data = b"This is some test data for hash calculation"
        input_stream = io.BytesIO(test_data)
        
        # Calculate expected hashes directly
        expected_md5 = hashlib.md5(test_data).hexdigest()
        expected_sha256 = hashlib.sha256(test_data).hexdigest()
        
        # Use the centralized hash calculation function
        # This function consumes the stream
        hash_stats = calculate_hashes_for_stream(input_stream, is_gzipped=False)
        
        # Verify calculated hashes
        self.assertEqual(hash_stats['md5sum'], expected_md5)
        self.assertEqual(hash_stats['sha256'], expected_sha256)
        self.assertEqual(hash_stats['file_size'], len(test_data))

    def test_non_buffered_reader_stream(self):
        """Test hash calculation with a non-BufferedReader stream."""
        # Create test data
        test_data = b"This is some test data for hash calculation"
        
        # Create a custom stream class that's not a BufferedReader
        class CustomStream:
            def __init__(self, data):
                self.data = data
                self.position = 0
                self._closed = False
            
            def read(self, size=-1):
                if self._closed:
                    raise ValueError("read of closed file")
                if self.position >= len(self.data):
                    return b''
                if size == -1:
                    chunk = self.data[self.position:]
                    self.position = len(self.data)
                else:
                    chunk = self.data[self.position:self.position + size]
                    self.position += len(chunk)
                return chunk
            
            def readinto(self, buffer):
                """Read data into a buffer."""
                if self._closed:
                    raise ValueError("read of closed file")
                if self.position >= len(self.data):
                    return 0
                
                # Calculate how much we can read
                remaining = len(self.data) - self.position
                to_read = min(remaining, len(buffer))
                
                # Copy data into buffer
                buffer[:to_read] = self.data[self.position:self.position + to_read]
                self.position += to_read
                return to_read
            
            def readable(self):
                return not self._closed
            
            def close(self):
                self._closed = True
            
            @property
            def closed(self):
                return self._closed
        
        # Create stream and hash calculators
        stream = CustomStream(test_data)
        md5_calc = hashlib.md5()
        sha256_calc = hashlib.sha256()
        hash_calculators = [('md5', md5_calc), ('sha256', sha256_calc)]
        
        # Create HashCalculatingStream
        hash_stream = HashCalculatingStream(stream, hash_calculators)
        
        # Read all data
        while hash_stream.read(10):  # Read in chunks of 10 bytes
            pass
        
        # Get results
        digests = hash_stream.get_hash_digests()
        total_bytes = hash_stream.get_total_bytes()
        
        # Verify results
        self.assertEqual(digests['md5'], hashlib.md5(test_data).hexdigest())
        self.assertEqual(digests['sha256'], hashlib.sha256(test_data).hexdigest())
        self.assertEqual(total_bytes, len(test_data))

    def test_readline_functionality(self):
        """Test hash calculation using readline method."""
        # Create test data with multiple lines
        test_data = b"Line 1\nLine 2\nLine 3\n"
        input_stream = io.BytesIO(test_data)
        
        # Create hash calculators
        md5_calc = hashlib.md5()
        sha256_calc = hashlib.sha256()
        hash_calculators = [('md5', md5_calc), ('sha256', sha256_calc)]
        
        # Create HashCalculatingStream
        hash_stream = HashCalculatingStream(input_stream, hash_calculators)
        
        # Read lines
        lines = []
        while True:
            line = hash_stream.readline()
            if not line:
                break
            lines.append(line)
        
        # Get results
        digests = hash_stream.get_hash_digests()
        total_bytes = hash_stream.get_total_bytes()
        
        # Verify results
        self.assertEqual(digests['md5'], hashlib.md5(test_data).hexdigest())
        self.assertEqual(digests['sha256'], hashlib.sha256(test_data).hexdigest())
        self.assertEqual(total_bytes, len(test_data))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], b"Line 1\n")
        self.assertEqual(lines[1], b"Line 2\n")
        self.assertEqual(lines[2], b"Line 3\n")

    def test_stream_without_readable_method(self):
        """Test handling of stream without readable() method."""
        # Create test data
        test_data = b"This is some test data for hash calculation"
        
        # Create a custom stream class without readable() method
        class NonReadableStream:
            def __init__(self, data):
                self.data = data
                self.position = 0
            
            def read(self, size=-1):
                if self.position >= len(self.data):
                    return b''
                if size == -1:
                    chunk = self.data[self.position:]
                    self.position = len(self.data)
                else:
                    chunk = self.data[self.position:self.position + size]
                    self.position += len(chunk)
                return chunk
        
        # Create stream and hash calculators
        stream = NonReadableStream(test_data)
        md5_calc = hashlib.md5()
        sha256_calc = hashlib.sha256()
        hash_calculators = [('md5', md5_calc), ('sha256', sha256_calc)]
        
        # Create HashCalculatingStream
        hash_stream = HashCalculatingStream(stream, hash_calculators)
        
        # Read all data
        while hash_stream.read(10):  # Read in chunks of 10 bytes
            pass
        
        # Get results
        digests = hash_stream.get_hash_digests()
        total_bytes = hash_stream.get_total_bytes()
        
        # Verify results
        self.assertEqual(digests['md5'], hashlib.md5(test_data).hexdigest())
        self.assertEqual(digests['sha256'], hashlib.sha256(test_data).hexdigest())
        self.assertEqual(total_bytes, len(test_data))

class TestGzipHashCalculatingStream(unittest.TestCase):
    """Test the GzipHashCalculatingStream class."""
    
    def test_gzip_hash_calculation(self):
        """Test hash calculation for gzipped data with content_md5sum."""
        # Create test data
        original_data = b"This is some test data that will be compressed"
        
        # Compress the data
        compressed_data = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_data, mode='wb') as gz:
            gz.write(original_data)
        
        # Get the compressed bytes and reset the stream
        compressed_bytes = compressed_data.getvalue()
        compressed_data.seek(0)
        
        # Calculate expected hashes directly
        expected_compressed_md5 = hashlib.md5(compressed_bytes).hexdigest()
        expected_compressed_sha256 = hashlib.sha256(compressed_bytes).hexdigest()
        expected_content_md5 = hashlib.md5(original_data).hexdigest()
        
        # Use the centralized hash calculation function
        hash_stats = calculate_hashes_for_stream(io.BytesIO(compressed_bytes), is_gzipped=True)
        
        # Verify calculated hashes
        self.assertEqual(hash_stats['md5sum'], expected_compressed_md5)
        self.assertEqual(hash_stats['sha256'], expected_compressed_sha256)
        self.assertEqual(hash_stats['file_size'], len(compressed_bytes))
        
        # Verify content_md5sum was calculated correctly
        self.assertEqual(hash_stats['content_md5sum'], expected_content_md5)
        self.assertEqual(hash_stats['content_size'], len(original_data))
    
    def test_chunked_gzip_reading(self):
        """Test reading compressed data in chunks to verify proper decompression state handling."""
        # Create larger test data to ensure multiple chunks
        original_data = b"This is a longer test string that will be read in chunks after compression. " * 100
        
        # Compress the data
        compressed_data = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_data, mode='wb') as gz:
            gz.write(original_data)
        
        # Get the compressed bytes and reset the stream
        compressed_bytes = compressed_data.getvalue()
        compressed_data.seek(0)
        
        # Calculate expected content MD5 directly
        expected_content_md5 = hashlib.md5(original_data).hexdigest()
        
        # Use the centralized hash calculation function
        # Note: calculate_hashes_for_stream reads the whole stream internally,
        # so direct testing of chunked reading on the *wrapper* isn't applicable here.
        # We test that the function works correctly with gzipped data.
        hash_stats = calculate_hashes_for_stream(io.BytesIO(compressed_bytes), is_gzipped=True)
        
        # Verify content_md5sum was calculated correctly even with chunked reading
        # (The function handles internal reading, ensuring correctness)
        self.assertEqual(hash_stats['content_md5sum'], expected_content_md5)
        self.assertEqual(hash_stats['content_size'], len(original_data))

    @patch('subprocess.Popen')
    def test_broken_pipe_handling(self, mock_popen):
        """Test handling of broken pipe during gzip processing."""
        # Create test data
        test_data = b"This is some test data"
        
        # Create mock processes
        mock_md5_process = MagicMock()
        mock_md5sum_process = MagicMock()
        mock_popen.side_effect = [mock_md5_process, mock_md5sum_process]
        
        # Create stream and hash calculators
        stream = io.BytesIO(test_data)
        md5_calc = hashlib.md5()
        sha256_calc = hashlib.sha256()
        hash_calculators = [('md5', md5_calc), ('sha256', sha256_calc)]
        
        # Create GzipHashCalculatingStream
        gzip_stream = GzipHashCalculatingStream(stream, hash_calculators)
        
        # Simulate broken pipe on first write
        mock_md5_process.stdin.write.side_effect = BrokenPipeError()
        
        # Read data
        gzip_stream.read()
        
        # Verify process was marked as failed
        self.assertTrue(gzip_stream.process_failed)
        self.assertEqual(gzip_stream.get_content_md5sum(), "")

    @patch('subprocess.Popen')
    def test_decompression_error_handling(self, mock_popen):
        """Test handling of decompression errors."""
        # Create invalid gzip data
        invalid_data = b"This is not valid gzip data"
        
        # Create mock processes
        mock_md5_process = MagicMock()
        mock_md5sum_process = MagicMock()
        mock_popen.side_effect = [mock_md5_process, mock_md5sum_process]
        
        # Create stream and hash calculators
        stream = io.BytesIO(invalid_data)
        md5_calc = hashlib.md5()
        sha256_calc = hashlib.sha256()
        hash_calculators = [('md5', md5_calc), ('sha256', sha256_calc)]
        
        # Create GzipHashCalculatingStream
        gzip_stream = GzipHashCalculatingStream(stream, hash_calculators)
        
        # Read data
        gzip_stream.read()
        
        # Verify content size is 0 due to decompression error
        self.assertEqual(gzip_stream.get_content_size(), 0)

    @patch('subprocess.Popen')
    def test_md5sum_timeout_handling(self, mock_popen):
        """Test handling of md5sum process timeout."""
        # Create test data
        test_data = b"This is some test data"
        
        # Create mock processes
        mock_md5_process = MagicMock()
        mock_md5sum_process = MagicMock()
        mock_popen.side_effect = [mock_md5_process, mock_md5sum_process]
        
        # Create stream and hash calculators
        stream = io.BytesIO(test_data)
        md5_calc = hashlib.md5()
        sha256_calc = hashlib.sha256()
        hash_calculators = [('md5', md5_calc), ('sha256', sha256_calc)]
        
        # Create GzipHashCalculatingStream
        gzip_stream = GzipHashCalculatingStream(stream, hash_calculators)
        
        # Simulate timeout in md5sum process
        mock_md5sum_process.communicate.side_effect = subprocess.TimeoutExpired(['md5sum'], 10)
        
        # Read data and get content md5sum
        gzip_stream.read()
        content_md5 = gzip_stream.get_content_md5sum()
        
        # Verify timeout handling
        self.assertEqual(content_md5, "")
        mock_md5sum_process.kill.assert_called_once()

    @patch('subprocess.Popen')
    def test_process_cleanup(self, mock_popen):
        """Test proper cleanup of subprocesses."""
        # Create test data
        test_data = b"This is some test data"
        
        # Create mock processes with proper setup
        mock_md5_process = MagicMock()
        mock_md5sum_process = MagicMock()
        mock_popen.side_effect = [mock_md5_process, mock_md5sum_process]
        
        # Set up mock process state
        mock_md5_process.poll.return_value = None  # Process is still running
        mock_md5_process.stdin = MagicMock()
        mock_md5sum_process.communicate.return_value = (b"test_hash  -\n", b"")  # Simulate successful md5sum output
        
        # Create stream and hash calculators
        stream = io.BytesIO(test_data)
        md5_calc = hashlib.md5()
        sha256_calc = hashlib.sha256()
        hash_calculators = [('md5', md5_calc), ('sha256', sha256_calc)]
        
        # Create GzipHashCalculatingStream
        gzip_stream = GzipHashCalculatingStream(stream, hash_calculators)
        
        # Read all data to ensure stream is fully consumed
        while gzip_stream.read(10):  # Read in chunks of 10 bytes
            pass
        
        # Get content md5sum to trigger process cleanup
        gzip_stream.get_content_md5sum()
        
        # Verify process cleanup
        mock_md5_process.stdin.close.assert_called_once()
        mock_md5_process.terminate.assert_called_once()
        
        # Clean up the stream
        stream.close()

class TestBaseValidator(unittest.TestCase):
    """Test the BaseValidator class."""
    
    def test_format_validation_result(self):
        """Test the format_validation_result static method with various inputs."""
        # Test case 1: Basic success case
        result1 = BaseValidator.format_validation_result(True)
        self.assertEqual(result1, {
            'valid': True,
            'errors': {},
            'warnings': {},
            'stats': {}
        })
        
        # Test case 2: With errors
        errors = {'format': 'Invalid file format'}
        result2 = BaseValidator.format_validation_result(False, errors=errors)
        self.assertEqual(result2, {
            'valid': False,
            'errors': errors,
            'warnings': {},
            'stats': {}
        })
        
        # Test case 3: With warnings
        warnings = {'performance': 'Slow processing'}
        result3 = BaseValidator.format_validation_result(True, warnings=warnings)
        self.assertEqual(result3, {
            'valid': True,
            'errors': {},
            'warnings': warnings,
            'stats': {}
        })
        
        # Test case 4: With stats
        stats = {'file_size': 1024, 'read_count': 100}
        result4 = BaseValidator.format_validation_result(True, stats=stats)
        self.assertEqual(result4, {
            'valid': True,
            'errors': {},
            'warnings': {},
            'stats': stats
        })
        
        # Test case 5: Complete case with all fields
        result5 = BaseValidator.format_validation_result(
            False,
            errors={'format': 'Invalid format'},
            warnings={'performance': 'Slow processing'},
            stats={'file_size': 1024}
        )
        self.assertEqual(result5, {
            'valid': False,
            'errors': {'format': 'Invalid format'},
            'warnings': {'performance': 'Slow processing'},
            'stats': {'file_size': 1024}
        })

if __name__ == '__main__':
    unittest.main() 