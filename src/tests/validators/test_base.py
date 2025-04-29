"""
Unit tests for base validator functionality.
"""

import io
import gzip
import hashlib
import unittest
from typing import Dict, Any

from src.validators.base import (
    HashCalculatingStream,
    GzipHashCalculatingStream,
    BaseValidator
)

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
        
        # Create validator to use its helper methods
        validator = BaseValidator()
        
        # Create hash calculating stream
        hash_stream, _ = validator.create_hash_calculating_stream(input_stream, is_gzipped=False)
        
        # Read all data from the stream to calculate hashes
        content = hash_stream.read()
        self.assertEqual(content, test_data)
        
        # Get calculated hash values
        hash_stats = validator.get_hash_values(hash_stream)
        
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
        
        # Create validator to use its helper methods
        validator = BaseValidator()
        
        # Create hash calculating stream for gzipped data
        hash_stream, _ = validator.create_hash_calculating_stream(io.BytesIO(compressed_bytes), is_gzipped=True)
        
        # Read all data from the stream to calculate hashes
        content = hash_stream.read()
        self.assertEqual(content, compressed_bytes)
        
        # Get calculated hash values
        hash_stats = validator.get_hash_values(hash_stream)
        
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
        
        # Create validator to use its helper methods
        validator = BaseValidator()
        
        # Create hash calculating stream for gzipped data
        hash_stream, _ = validator.create_hash_calculating_stream(io.BytesIO(compressed_bytes), is_gzipped=True)
        
        # Read data in small chunks (512 bytes)
        chunk_size = 512
        chunks = []
        while True:
            chunk = hash_stream.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
        
        # Get calculated hash values
        hash_stats = validator.get_hash_values(hash_stream)
        
        # Verify content_md5sum was calculated correctly even with chunked reading
        self.assertEqual(hash_stats['content_md5sum'], expected_content_md5)
        self.assertEqual(hash_stats['content_size'], len(original_data))

if __name__ == '__main__':
    unittest.main() 