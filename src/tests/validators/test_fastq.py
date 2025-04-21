"""
Tests for the FASTQ validator, testing both Rust and SeqKit implementations.
"""
import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import io

from src.validators.fastq import FastqValidator, RUST_AVAILABLE
from src.wrappers.seqkit import SeqKitError

# Check if the Rust extension is available
try:
    import fastq_validator
    RUST_INSTALLED = True
    print("Rust FASTQ validator is available for testing")
except ImportError:
    RUST_INSTALLED = False
    print("Rust FASTQ validator is not available - skipping Rust tests")

class TestFastqValidator(unittest.TestCase):
    """Test cases for the FASTQ validator."""
    
    def setUp(self):
        """Set up the test environment."""
        self.validator = FastqValidator()
        
        # Create a temporary FASTQ file for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_fastq = os.path.join(self.temp_dir.name, "test.fastq")
        
        # Create a simple FASTQ file
        with open(self.temp_fastq, "w") as f:
            f.write("@read1\n")
            f.write("ACGTACGT\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            f.write("@read2\n")
            f.write("GCTAGCTA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
    
    def tearDown(self):
        """Clean up after the tests."""
        self.temp_dir.cleanup()
    
    # SeqKit Tests
    
    @patch('src.validators.fastq.RUST_AVAILABLE', False)
    @patch('src.wrappers.seqkit.SeqKitWrapper.stats')
    @patch('src.wrappers.seqkit.SeqKitWrapper.head')
    def test_validate_file_valid_seqkit(self, mock_head, mock_stats):
        """Test validating a valid FASTQ file with SeqKit."""
        # Mock the SeqKit methods
        mock_stats.return_value = {
            "read_count": 2,
            "total_length": 16,
            "min_length": 8,
            "avg_length": 8.0,
            "max_length": 8
        }
        
        # Validate the file
        result = self.validator.validate_file(self.temp_fastq)
        
        # Verify the results
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
    
    @patch('src.validators.fastq.RUST_AVAILABLE', False)
    @patch('src.wrappers.seqkit.SeqKitWrapper.stats')
    @patch('src.wrappers.seqkit.SeqKitWrapper.head')
    def test_validate_file_empty_seqkit(self, mock_head, mock_stats):
        """Test validating an empty FASTQ file with SeqKit."""
        # Mock the SeqKit methods
        mock_stats.return_value = {
            "read_count": 0,
            "total_length": 0,
            "min_length": 0,
            "avg_length": 0,
            "max_length": 0
        }
        
        # Validate the file
        result = self.validator.validate_file(self.temp_fastq)
        
        # Verify the results
        self.assertFalse(result["valid"])
        self.assertIn("empty_file", result["errors"])
    
    @patch('src.validators.fastq.RUST_AVAILABLE', False)
    @patch('src.wrappers.seqkit.SeqKitWrapper.stats')
    @patch('src.wrappers.seqkit.SeqKitWrapper.head')
    def test_validate_file_short_reads_seqkit(self, mock_head, mock_stats):
        """Test validating a FASTQ file with short reads using SeqKit."""
        # Mock the SeqKit methods
        mock_stats.return_value = {
            "read_count": 2,
            "total_length": 10,
            "min_length": 4,
            "avg_length": 5.0,
            "max_length": 6
        }
        
        # Validate the file
        result = self.validator.validate_file(self.temp_fastq)
        
        # Verify the results
        self.assertTrue(result["valid"])  # Short reads are a warning, not an error
        self.assertIn("short_reads", result["warnings"])
    
    @patch('src.validators.fastq.RUST_AVAILABLE', False)
    @patch('src.wrappers.seqkit.SeqKitWrapper.head')
    def test_validate_file_format_error_seqkit(self, mock_head):
        """Test validating an invalid FASTQ file with SeqKit."""
        # Mock the head method to raise an error
        mock_head.side_effect = SeqKitError("Invalid FASTQ format")
        
        # Validate the file
        result = self.validator.validate_file(self.temp_fastq)
        
        # Verify the results
        self.assertFalse(result["valid"])
        self.assertIn("invalid_format", result["errors"])
    
    def test_validate_file_not_found(self):
        """Test validating a non-existent file."""
        # Validate a non-existent file
        result = self.validator.validate_file("/path/to/nonexistent/file.fastq")
        
        # Verify the results
        self.assertFalse(result["valid"])
        self.assertIn("file_not_found", result["errors"])
    
    @patch('src.validators.fastq.RUST_AVAILABLE', False)
    @patch('src.wrappers.seqkit.SeqKitWrapper.validate_fastq_streaming')
    def test_validate_stream_valid_seqkit(self, mock_validate):
        """Test validating a valid FASTQ stream with SeqKit."""
        # Mock the validate_fastq_streaming method
        mock_validate.return_value = {
            "valid": True,
            "stats": {
                "read_count": 2,
                "total_length": 16,
                "min_length": 8,
                "avg_length": 8.0,
                "max_length": 8
            }
        }
        
        # Create a mock input stream
        input_stream = io.BytesIO(b"@read1\nACGT\n+\nIIII\n@read2\nACGT\n+\nIIII\n")
        
        # Validate the stream
        result = self.validator.validate_stream(input_stream)
        
        # Verify the results
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
    
    @patch('src.validators.fastq.RUST_AVAILABLE', False)
    @patch('src.wrappers.seqkit.SeqKitWrapper.validate_fastq_streaming')
    def test_validate_stream_invalid_seqkit(self, mock_validate):
        """Test validating an invalid FASTQ stream with SeqKit."""
        # Mock the validate_fastq_streaming method
        mock_validate.return_value = {
            "valid": False,
            "error": "Invalid FASTQ format"
        }
        
        # Create a mock input stream
        input_stream = io.BytesIO(b"This is not a valid FASTQ file")
        
        # Validate the stream
        result = self.validator.validate_stream(input_stream)
        
        # Verify the results
        self.assertFalse(result["valid"])
        self.assertIn("invalid_format", result["errors"])
    
    # Rust Tests - Only run these if Rust is installed
    
    @unittest.skipIf(not RUST_INSTALLED, "Rust extension not available")
    @patch('src.validators.fastq.RUST_AVAILABLE', True)
    @patch('fastq_validator.validate_fastq')
    @patch('fastq_validator.fastq_stats')
    def test_validate_file_valid_rust(self, mock_stats, mock_validate):
        """Test validating a valid FASTQ file with Rust."""
        # Mock the Rust methods
        mock_validate.return_value = True
        mock_stats.return_value = {
            "read_count": 2,
            "min_length": 8,
            "max_length": 8,
            "avg_length": 8.0,
            "total_length": 16
        }
        
        # Validate the file
        result = self.validator.validate_file(self.temp_fastq)
        
        # Verify the results
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
        
        # Verify Rust functions were called
        mock_validate.assert_called_once_with(self.temp_fastq)
        mock_stats.assert_called_once_with(self.temp_fastq)
    
    @unittest.skipIf(not RUST_INSTALLED, "Rust extension not available")
    @patch('src.validators.fastq.RUST_AVAILABLE', True)
    @patch('fastq_validator.validate_fastq')
    def test_validate_file_invalid_rust(self, mock_validate):
        """Test validating an invalid FASTQ file with Rust."""
        # Mock the Rust method to indicate invalid file
        mock_validate.return_value = False
        
        # Validate the file
        result = self.validator.validate_file(self.temp_fastq)
        
        # Verify the results
        self.assertFalse(result["valid"])
        self.assertIn("invalid_format", result["errors"])
        
        # Verify Rust function was called
        mock_validate.assert_called_once_with(self.temp_fastq)
    
    @unittest.skipIf(not RUST_INSTALLED, "Rust extension not available")
    @patch('src.validators.fastq.RUST_AVAILABLE', True)
    @patch('fastq_validator.validate_fastq_from_bytes')
    @patch('fastq_validator.fastq_stats_from_bytes')
    def test_validate_stream_valid_rust(self, mock_stats, mock_validate):
        """Test validating a valid FASTQ stream with Rust."""
        # Mock the Rust methods
        mock_validate.return_value = True
        mock_stats.return_value = {
            "read_count": 2,
            "min_length": 8,
            "max_length": 8,
            "avg_length": 8.0,
            "total_length": 16
        }
        
        # Create a mock input stream
        input_stream = io.BytesIO(b"@read1\nACGT\n+\nIIII\n@read2\nACGT\n+\nIIII\n")
        
        # Validate the stream
        result = self.validator.validate_stream(input_stream)
        
        # Verify the results
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
        
        # Verify Rust functions were called (can't verify exact arguments due to BytesIO)
        mock_validate.assert_called_once()
        mock_stats.assert_called_once()
        
    @unittest.skipIf(not RUST_INSTALLED, "Rust extension not available")
    @patch('src.validators.fastq.RUST_AVAILABLE', True)
    @patch('fastq_validator.validate_fastq_from_bytes')
    def test_validate_stream_invalid_rust(self, mock_validate):
        """Test validating an invalid FASTQ stream with Rust."""
        # Mock the Rust method to indicate invalid stream
        mock_validate.return_value = False
        
        # Create a mock input stream
        input_stream = io.BytesIO(b"This is not a valid FASTQ file")
        
        # Validate the stream
        result = self.validator.validate_stream(input_stream)
        
        # Verify the results
        self.assertFalse(result["valid"])
        self.assertIn("invalid_format", result["errors"])
        
        # Verify Rust function was called
        mock_validate.assert_called_once()

if __name__ == "__main__":
    unittest.main()