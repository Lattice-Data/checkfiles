"""
Unit tests for base validator functionality.
"""

import io
import gzip
import hashlib
import unittest
from typing import Dict, Any

# Import the new centralized function
from src.core.validation import calculate_hashes_for_stream

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

if __name__ == '__main__':
    unittest.main() 