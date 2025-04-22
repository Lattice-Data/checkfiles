"""
Tests for the FASTQ validator with Rust implementation.
"""
import os
import unittest
import tempfile
import io

from src.validators.fastq import FastqValidator

# Import Rust validator to check availability
try:
    import fastq_validator
    RUST_INSTALLED = True
except ImportError:
    RUST_INSTALLED = False
    print("Rust FASTQ validator is not available - tests cannot proceed")


@unittest.skipIf(not RUST_INSTALLED, "Rust FASTQ validator is required for these tests")
class TestFastqValidator(unittest.TestCase):
    """Test cases for the FASTQ validator."""
    
    def setUp(self):
        """Set up the test environment."""
        self.validator = FastqValidator()
        
        # Create a temporary FASTQ file for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_fastq = os.path.join(self.temp_dir.name, "test.fastq")
        
        # Create a simple valid FASTQ file
        with open(self.temp_fastq, "w") as f:
            f.write("@read1\n")
            f.write("ACGTACGT\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            f.write("@read2\n")
            f.write("GCTAGCTA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
        
        # Create an invalid FASTQ file for testing
        self.invalid_fastq = os.path.join(self.temp_dir.name, "invalid.fastq")
        with open(self.invalid_fastq, "w") as f:
            f.write("Not a FASTQ file\n")
            f.write("Just some random text\n")
    
    def tearDown(self):
        """Clean up after the tests."""
        self.temp_dir.cleanup()
    
    def test_validate_file_valid(self):
        """Test validating a valid FASTQ file."""
        result = self.validator.validate_file(self.temp_fastq)
        
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
        
        # Verify statistics
        stats = result["stats"]
        self.assertEqual(stats["read_count"], 2)
        self.assertEqual(stats["total_length"], 16)
        self.assertEqual(stats["min_length"], 8)
        self.assertEqual(stats["max_length"], 8)
    
    def test_validate_file_invalid(self):
        """Test validating an invalid FASTQ file."""
        result = self.validator.validate_file(self.invalid_fastq)
        
        self.assertFalse(result["valid"])
        self.assertIn("invalid_format", result["errors"])
    
    def test_validate_file_not_found(self):
        """Test validating a non-existent file."""
        result = self.validator.validate_file("/path/to/nonexistent/file.fastq")
        
        self.assertFalse(result["valid"])
        self.assertIn("file_not_found", result["errors"])
    
    def test_validate_stream_valid(self):
        """Test validating a valid FASTQ stream."""
        # Create a valid FASTQ stream
        stream_content = b"@read1\nACGT\n+\nIIII\n@read2\nACGT\n+\nIIII\n"
        input_stream = io.BytesIO(stream_content)
        
        result = self.validator.validate_stream(input_stream)
        
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
        
        # Verify statistics
        stats = result["stats"]
        self.assertEqual(stats["read_count"], 2)
        self.assertEqual(stats["total_length"], 8)
        self.assertEqual(stats["min_length"], 4)
        self.assertEqual(stats["max_length"], 4)
    
    def test_validate_stream_invalid(self):
        """Test validating an invalid FASTQ stream."""
        # Create an invalid stream
        stream_content = b"This is not a valid FASTQ file"
        input_stream = io.BytesIO(stream_content)
        
        result = self.validator.validate_stream(input_stream)
        
        self.assertFalse(result["valid"])
        self.assertIn("invalid_format", result["errors"])
    
    def test_validate_empty_file(self):
        """Test validating an empty FASTQ file."""
        # Create an empty file
        empty_fastq = os.path.join(self.temp_dir.name, "empty.fastq")
        with open(empty_fastq, "w") as f:
            pass
        
        result = self.validator.validate_file(empty_fastq)
        
        self.assertFalse(result["valid"])
        self.assertIn("empty_file", result["errors"])
    
    def test_validate_short_reads(self):
        """Test validating FASTQ with very short reads."""
        # Create a FASTQ file with short reads
        short_fastq = os.path.join(self.temp_dir.name, "short.fastq")
        with open(short_fastq, "w") as f:
            f.write("@read1\n")
            f.write("AC\n")  # Very short read
            f.write("+\n")
            f.write("II\n")
        
        result = self.validator.validate_file(short_fastq)
        
        self.assertTrue(result["valid"])  # Short reads are a warning, not an error
        self.assertIn("short_reads", result["warnings"])
    
    def test_validate_variable_length_reads(self):
        """Test validating FASTQ with variable length reads."""
        # Create a FASTQ file with variable length reads
        var_fastq = os.path.join(self.temp_dir.name, "variable.fastq")
        with open(var_fastq, "w") as f:
            f.write("@read1\n")
            f.write("ACGT\n")
            f.write("+\n")
            f.write("IIII\n")
            f.write("@read2\n")
            f.write("ACGTACGTACGT\n")  # 3x longer read
            f.write("+\n")
            f.write("IIIIIIIIIIII\n")
        
        result = self.validator.validate_file(var_fastq)
        
        self.assertTrue(result["valid"])
        self.assertIn("variable_length", result["warnings"])


if __name__ == "__main__":
    unittest.main()