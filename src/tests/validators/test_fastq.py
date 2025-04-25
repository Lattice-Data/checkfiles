"""
Tests for the FASTQ validator with pure Python implementation.
"""
import os
import unittest
import tempfile
import io

from src.validators.fastq import FastqValidator

# Get the path to test data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "data", "fastq")
VALID_FILES_DIR = os.path.join(TEST_DATA_DIR, "valid")
INVALID_FILES_DIR = os.path.join(TEST_DATA_DIR, "invalid")


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

    def test_error_message_content(self):
        """Test that specific error messages are included in the validation results."""
        # Create a file with a specific error - header line without @
        bad_header_fastq = os.path.join(self.temp_dir.name, "bad_header.fastq")
        with open(bad_header_fastq, "w") as f:
            f.write("read1 without @ symbol\n")  # Missing @ in header
            f.write("ACGT\n")
            f.write("+\n")
            f.write("IIII\n")
        
        result = self.validator.validate_file(bad_header_fastq)
        
        self.assertFalse(result["valid"])
        # Verify the error message contains specific information
        self.assertIn("Header line must start with @", result["errors"]["invalid_format"])
        # Verify the line number is reported
        self.assertIn("at line 1", result["errors"]["invalid_format"])
    
    def test_line_number_reporting(self):
        """Test that line numbers are correctly reported in validation errors."""
        # Create a file with an error in a specific line
        line_error_fastq = os.path.join(self.temp_dir.name, "line_error.fastq")
        with open(line_error_fastq, "w") as f:
            f.write("@read1\n")
            f.write("ACGT\n")
            f.write("+\n")
            f.write("IIII\n")
            f.write("@read2\n")
            f.write("ACGT\n")
            f.write("MISSING_PLUS_SYMBOL\n")  # Error on line 7 - missing +
            f.write("IIII\n")
        
        result = self.validator.validate_file(line_error_fastq)
        
        self.assertFalse(result["valid"])
        # Check that line 7 is mentioned in the error message
        self.assertIn("at line 7", result["errors"]["invalid_format"])
    
    def test_stream_error_details(self):
        """Test that stream validation provides detailed error information."""
        # Create a stream with a specific error - quality length mismatch
        stream_content = b"@read1\nACGTACGT\n+\nIII\n"  # Quality length (3) doesn't match sequence (8)
        input_stream = io.BytesIO(stream_content)
        
        result = self.validator.validate_stream(input_stream)
        
        self.assertFalse(result["valid"])
        # Verify error contains details about the length mismatch
        self.assertIn("length", result["errors"]["invalid_format"].lower())
        self.assertIn("don't match", result["errors"]["invalid_format"])


class TestFastqValidatorEnhanced(unittest.TestCase):
    """Enhanced test cases for the FASTQ validator using the test data directory."""
    
    def setUp(self):
        """Set up the test environment."""
        self.validator = FastqValidator()
        
        # Skip tests if test data directory doesn't exist
        if not os.path.exists(TEST_DATA_DIR):
            self.skipTest(f"Test data directory not found: {TEST_DATA_DIR}")
    
    def test_all_valid_files(self):
        """Test validating all valid FASTQ files in the test data directory."""
        if not os.path.exists(VALID_FILES_DIR):
            self.skipTest(f"Valid files directory not found: {VALID_FILES_DIR}")
        
        valid_files = [f for f in os.listdir(VALID_FILES_DIR) if f.endswith('.fastq')]
        
        for filename in valid_files:
            file_path = os.path.join(VALID_FILES_DIR, filename)
            result = self.validator.validate_file(file_path)
            
            self.assertTrue(result["valid"], f"File should be valid: {filename}")
            self.assertEqual(len(result["errors"]), 0, f"No errors should be present for: {filename}")
    
    def test_all_invalid_files(self):
        """Test validating all invalid FASTQ files in the test data directory."""
        if not os.path.exists(INVALID_FILES_DIR):
            self.skipTest(f"Invalid files directory not found: {INVALID_FILES_DIR}")
        
        invalid_files = [f for f in os.listdir(INVALID_FILES_DIR) if f.endswith('.fastq')]
        
        for filename in invalid_files:
            file_path = os.path.join(INVALID_FILES_DIR, filename)
            result = self.validator.validate_file(file_path)
            
            self.assertFalse(result["valid"], f"File should be invalid: {filename}")
            self.assertGreater(len(result["errors"]), 0, f"Errors should be present for: {filename}")
    
    def test_mismatched_lengths(self):
        """Test validating a FASTQ file with mismatched sequence/quality lengths."""
        # Create a file with mismatched lengths
        with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
            f.write(b"@read1\n")
            f.write(b"ACGTACGT\n")
            f.write(b"+\n")
            f.write(b"IIII\n")  # Quality line too short
        
        try:
            result = self.validator.validate_file(f.name)
            self.assertFalse(result["valid"])
            self.assertIn("length", result["errors"]["invalid_format"].lower())
        finally:
            os.unlink(f.name)
    
    def test_missing_at_symbol(self):
        """Test validating a FASTQ file with missing @ in header."""
        with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
            f.write(b"read1\n")  # Missing @ in header
            f.write(b"ACGTACGT\n")
            f.write(b"+\n")
            f.write(b"IIIIIIII\n")
        
        try:
            result = self.validator.validate_file(f.name)
            self.assertFalse(result["valid"])
            self.assertIn("Header line must start with @", result["errors"]["invalid_format"])
        finally:
            os.unlink(f.name)
    
    def test_missing_plus(self):
        """Test validating a FASTQ file with missing + line."""
        with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
            f.write(b"@read1\n")
            f.write(b"ACGTACGT\n")
            f.write(b"MISSING_PLUS\n")  # Missing + character
            f.write(b"IIIIIIII\n")
        
        try:
            result = self.validator.validate_file(f.name)
            self.assertFalse(result["valid"])
            self.assertIn("Quality header must start with +", result["errors"]["invalid_format"])
        finally:
            os.unlink(f.name)
    
    def test_mismatched_ids(self):
        """Test validating a FASTQ file with mismatched IDs in header and + line."""
        with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
            f.write(b"@read1\n")
            f.write(b"ACGTACGT\n")
            f.write(b"+read2\n")  # Different ID than header
            f.write(b"IIIIIIII\n")
        
        try:
            result = self.validator.validate_file(f.name)
            self.assertFalse(result["valid"])
            self.assertIn("Seqname in + line", result["errors"]["invalid_format"])
        finally:
            os.unlink(f.name)
    
    def test_incomplete_record(self):
        """Test validating a FASTQ file with incomplete records."""
        with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
            f.write(b"@read1\n")
            f.write(b"ACGTACGT\n")
            f.write(b"+\n")
            # Missing quality line
        
        try:
            result = self.validator.validate_file(f.name)
            self.assertFalse(result["valid"])
            self.assertIn("Incomplete FASTQ block", result["errors"]["invalid_format"])
        finally:
            os.unlink(f.name)
    
    def test_stream_with_large_data(self):
        """Test validating a large data stream."""
        # Create a moderately large FASTQ stream (10,000 reads)
        buffer = io.BytesIO()
        for i in range(10_000):
            buffer.write(f"@read{i}\n".encode())
            buffer.write(b"ACGTACGTACGTACGT\n")
            buffer.write(f"+read{i}\n".encode())
            buffer.write(b"IIIIIIIIIIIIIIII\n")
        
        buffer.seek(0)
        result = self.validator.validate_stream(buffer)
        
        self.assertTrue(result["valid"])
        self.assertEqual(result["stats"]["read_count"], 10_000)
    
    def test_with_descriptions(self):
        """Test validating a FASTQ file with varying descriptions in headers."""
        with tempfile.NamedTemporaryFile(suffix=".fastq", delete=False) as f:
            f.write(b"@A00887:459:HWFCYDRXY:1:1101:1125:1000 1:N:0:GTAGAGGA+CTAAGCCT\n")
            f.write(b"ACTG\n")
            f.write(b"+\n")
            f.write(b"IIII\n")
            f.write(b"@A00887:459:HWFCYDRXY:1:1101:1554:1000 1:N:0:GTAGAGGA+CTAAGCCT\n")
            f.write(b"CAGT\n")
            f.write(b"+\n")
            f.write(b"IIII\n")
        
        try:
            result = self.validator.validate_file(f.name)
            self.assertTrue(result["valid"])
            self.assertEqual(result["stats"]["read_count"], 2)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()