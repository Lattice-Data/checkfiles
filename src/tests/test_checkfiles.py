import unittest
from unittest.mock import patch, Mock, MagicMock
import io
import sys
import os
import tempfile
import gzip
import zlib
from pathlib import Path
import hashlib
import crcmod.predefined
import subprocess

# Add the parent directory to path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.checkfiles import (
    has_gz_extension, 
    initialize_validator,
    validate_local_file,
    validate_s3_file,
    stream_s3_file,
    SimpleActivityTracker,
    validate_gzip_format
)

class TestCheckfiles(unittest.TestCase):
    
    def setUp(self):
        # Create test files
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create a valid FASTQ file
        self.valid_fastq_path = Path(self.temp_dir.name) / "valid.fastq"
        with open(self.valid_fastq_path, 'w') as f:
            f.write("@SRR001666.1 071112_SLXA-EAS1_s_7:5:1:817:345 length=36\n")
            f.write("GGGTGATGGCCGCTGCCGATGGCGTCAAATCCCACC\n")
            f.write("+SRR001666.1 071112_SLXA-EAS1_s_7:5:1:817:345 length=36\n")
            f.write("IIIIIIIIIIIIIIIIIIIIIIIIIIIIII9IG9IC\n")
        
        # Create a gzipped FASTQ file
        self.gzipped_fastq_path = Path(self.temp_dir.name) / "test.fastq.gz"
        with gzip.open(self.gzipped_fastq_path, 'wb') as f:
            f.write(b"@SRR001666.1 071112_SLXA-EAS1_s_7:5:1:817:345 length=36\n")
            f.write(b"GGGTGATGGCCGCTGCCGATGGCGTCAAATCCCACC\n")
            f.write(b"+SRR001666.1 071112_SLXA-EAS1_s_7:5:1:817:345 length=36\n")
            f.write(b"IIIIIIIIIIIIIIIIIIIIIIIIIIIIII9IG9IC\n")
        
        # Create an invalid FASTQ file (wrong quality line length)
        self.invalid_fastq_path = Path(self.temp_dir.name) / "invalid.fastq"
        with open(self.invalid_fastq_path, 'w') as f:
            f.write("@SRR001666.1 071112_SLXA-EAS1_s_7:5:1:817:345 length=36\n")
            f.write("GGGTGATGGCCGCTGCCGATGGCGTCAAATCCCACC\n")
            f.write("+SRR001666.1 071112_SLXA-EAS1_s_7:5:1:817:345 length=36\n")
            f.write("IIIIIIIIIIIIIIIIIIIIIIII\n")  # Too short quality line
            
        # Create a valid gzipped file
        self.valid_gz_path = Path(self.temp_dir.name) / "test.gz"
        with gzip.open(self.valid_gz_path, 'wb') as f:
            f.write(b"test content")
        
        # Create an invalid gzipped file (corrupted header)
        self.invalid_gz_path = Path(self.temp_dir.name) / "invalid.gz"
        with open(self.invalid_gz_path, 'wb') as f:
            # Write valid gzip header but with invalid compression method
            f.write(b'\x1f\x8b')  # Magic number
            f.write(b'\x09')      # Invalid compression method (valid is 0x08)
            f.write(b'\x00')      # Flags
            f.write(b'\x00\x00\x00\x00')  # Timestamp
            f.write(b'\x00')      # Extra flags
            f.write(b'\x00')      # OS
            f.write(b'invalid content')
        
        # Create a non-gzipped file with .gz extension
        self.fake_gz_path = Path(self.temp_dir.name) / "fake.gz"
        with open(self.fake_gz_path, 'wb') as f:
            f.write(b'not a gzipped file')
            
    def tearDown(self):
        # Clean up temp files
        self.temp_dir.cleanup()
    
    def test_has_gz_extension(self):
        self.assertTrue(has_gz_extension("file.gz"))
        self.assertTrue(has_gz_extension("file.fastq.gz"))
        self.assertTrue(has_gz_extension("file.GZIP"))
        self.assertFalse(has_gz_extension("file.txt"))
        self.assertFalse(has_gz_extension("file.fastq"))
    
    @patch('src.validators.fastq.FastqValidator')
    def test_initialize_validator_fastq(self, mock_fastq_validator):
        # Setup mock
        mock_instance = Mock()
        mock_fastq_validator.return_value = mock_instance
        
        # We need to patch the import inside initialize_validator
        with patch('builtins.__import__', side_effect=self._mock_import_fastq(mock_fastq_validator)):
            # Test fastq validator initialization
            validator = initialize_validator("fastq")
            self.assertEqual(validator, mock_instance)
            mock_fastq_validator.assert_called_once()
            
            # Test case insensitivity
            initialize_validator("FASTQ")
            self.assertEqual(mock_fastq_validator.call_count, 2)

    def _mock_import_fastq(self, mock_fastq_validator):
        """Helper to mock the import of FastqValidator"""
        original_import = __import__
        
        def import_mock(name, *args, **kwargs):
            if name == 'src.validators.fastq':
                module = Mock()
                module.FastqValidator = mock_fastq_validator
                return module
            return original_import(name, *args, **kwargs)
        
        return import_mock
    
    def test_initialize_validator_unsupported(self):
        with self.assertRaises(ValueError) as context:
            initialize_validator("unsupported_format")
        
        self.assertIn("Unsupported file format", str(context.exception))
    
    @patch('src.validators.fastq.FastqValidator')
    def test_validate_local_file_success(self, mock_fastq_validator):
        # Setup mock validator
        mock_instance = Mock()
        mock_instance.validate_file.return_value = {"valid": True, "records": 1}
        mock_instance.validate_stream.return_value = {"valid": True, "records": 1}
        mock_fastq_validator.return_value = mock_instance
        
        # Test with regular file
        result = validate_local_file(
            str(self.valid_fastq_path),
            "fastq",
            validator=mock_instance
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["file_path"], str(self.valid_fastq_path))
        self.assertTrue(result["results"]["valid"])
        mock_instance.validate_file.assert_called_once_with(str(self.valid_fastq_path))
        
        # Test with gzipped file
        result = validate_local_file(
            str(self.gzipped_fastq_path),
            "fastq",
            validator=mock_instance
        )
        
        self.assertTrue(result["success"])
        mock_instance.validate_stream.assert_called_once()
    
    @patch('src.validators.fastq.FastqValidator')
    def test_validate_local_file_with_tracker(self, mock_fastq_validator):
        # Setup mock validator
        mock_instance = Mock()
        mock_instance.validate_file.return_value = {"valid": True, "records": 1}
        mock_fastq_validator.return_value = mock_instance
        
        # Setup mock progress tracker
        mock_tracker = Mock(spec=SimpleActivityTracker)
        
        # Test validation with tracker
        result = validate_local_file(
            str(self.valid_fastq_path),
            "fastq",
            validator=mock_instance,
            progress_tracker=mock_tracker
        )
        
        self.assertTrue(result["success"])
        mock_tracker.init_file.assert_called_once_with(str(self.valid_fastq_path))
        self.assertGreaterEqual(mock_tracker.update_progress.call_count, 1)
        mock_tracker.complete_file.assert_called_once()
    
    @patch('src.validators.fastq.FastqValidator')
    def test_validate_local_file_exception(self, mock_fastq_validator):
        # Setup mock validator
        mock_instance = Mock()
        mock_instance.validate_file.side_effect = Exception("Test error")
        mock_fastq_validator.return_value = mock_instance
        
        # Test validation failure
        result = validate_local_file(
            str(self.valid_fastq_path),
            "fastq",
            validator=mock_instance
        )
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("Test error", result["error"])
    
    @patch('src.checkfiles.stream_s3_file')
    @patch('src.validators.fastq.FastqValidator')
    def test_validate_s3_file_success(self, mock_fastq_validator, mock_stream_s3):
        # Setup mocks for stream and validator
        mock_stream = MagicMock(spec=io.BytesIO)
        mock_stream.read.side_effect = [b'test data', b'']  # Return data then EOF
        
        mock_validator = Mock()
        mock_validator.validate_stream.return_value = {"valid": True, "records": 1}
        
        # Create mock hash objects
        mock_md5 = MagicMock(spec=hashlib.md5())
        mock_md5.hexdigest.return_value = "a1b2c3d4"
        
        mock_sha256 = MagicMock(spec=hashlib.sha256())
        mock_sha256.hexdigest.return_value = "e5f6g7h8"
        
        # Mock crcmod.predefined.Crc
        mock_crc32c = Mock()
        mock_crc32c.crcValue = 0x12345678
        mock_crc_func = Mock(return_value=mock_crc32c)
        
        # Test with all mocked components
        with patch('src.checkfiles.stream_s3_file', return_value=mock_stream):
            with patch('src.checkfiles.initialize_validator', return_value=mock_validator):
                with patch('src.checkfiles.hashlib.md5', return_value=mock_md5):
                    with patch('src.checkfiles.hashlib.sha256', return_value=mock_sha256):
                        with patch('crcmod.predefined.Crc', mock_crc_func):
                            result = validate_s3_file(
                                "s3://bucket/test.fastq",
                                "fastq"
                            )
        
        self.assertTrue(result["success"])
        self.assertTrue(result["results"]["valid"])
        mock_validator.validate_stream.assert_called_once()
        
        # Check that hashes were calculated
        self.assertIn("md5sum", result["results"])
        self.assertIn("sha256", result["results"])
        self.assertIn("crc32c", result["results"])
        mock_crc_func.assert_called_with('crc-32c')
    
    @patch('src.checkfiles.subprocess.Popen')
    def test_stream_s3_file(self, mock_popen):
        # Setup mock process
        mock_process = Mock()
        mock_process.stdout = Mock()
        mock_popen.return_value = mock_process
        
        # Test non-gzipped file
        stream_s3_file("s3://bucket/file.fastq")
        mock_popen.assert_called_with(
            "aws s3 cp s3://bucket/file.fastq -",
            shell=True,
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY
        )
        
        # Test gzipped file
        mock_popen.reset_mock()
        stream_s3_file("s3://bucket/file.fastq.gz")
        mock_popen.assert_called_with(
            "aws s3 cp s3://bucket/file.fastq.gz - | gunzip -c",
            shell=True,
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY
        )
    
    @patch('src.checkfiles.subprocess.Popen')
    def test_stream_s3_file_error(self, mock_popen):
        # Setup mock to raise exception
        mock_popen.side_effect = Exception("Connection error")
        
        # Test error handling
        result = stream_s3_file("s3://bucket/file.fastq")
        self.assertIsNone(result)

    def test_simple_activity_tracker(self):
        # Test basic tracker functionality
        tracker = SimpleActivityTracker(2)
        self.assertEqual(tracker.total_files, 2)
        self.assertEqual(tracker.completed, 0)
        
        # Test file initialization
        tracker.init_file("test_file.fastq")
        self.assertIn("test_file.fastq", tracker.file_status)
        self.assertEqual(tracker.file_status["test_file.fastq"]["status"], "Starting...")
        
        # Test progress update
        tracker.update_progress("test_file.fastq", "Processing")
        self.assertEqual(tracker.file_status["test_file.fastq"]["status"], "Processing")
        
        # Test file completion
        tracker.complete_file("test_file.fastq", True, {"valid": True})
        self.assertEqual(tracker.completed, 1)
        self.assertTrue(tracker.file_status["test_file.fastq"]["complete"])
        self.assertTrue(tracker.file_status["test_file.fastq"]["success"])

    def test_validate_gzip_format_valid_local(self):
        """Test validation of a valid local gzip file"""
        result = validate_gzip_format(str(self.valid_gz_path))
        self.assertEqual(result, {}, "Valid gzip file should return empty error dict")

    def test_validate_gzip_format_invalid_magic_number_local(self):
        """Test validation of a local file with invalid gzip magic number"""
        result = validate_gzip_format(str(self.fake_gz_path))
        self.assertIn('gzip_error', result)
        self.assertIn('magic number', result['gzip_error'].lower())

    def test_validate_gzip_format_invalid_header_local(self):
        """Test validation of a local file with invalid gzip header"""
        result = validate_gzip_format(str(self.invalid_gz_path))
        self.assertIn('gzip_error', result)
        # The error message could mention either 'header', 'compression method', or 'format'
        error_msg = result['gzip_error'].lower()
        self.assertTrue(
            any(msg in error_msg for msg in ['header', 'compression method', 'format']),
            f"Expected error message to mention header issues, got: {error_msg}"
        )

    def test_validate_gzip_format_nonexistent_file(self):
        """Test validation of a nonexistent file"""
        result = validate_gzip_format(str(Path(self.temp_dir.name) / "nonexistent.gz"))
        self.assertIn('gzip_error', result)
        self.assertIn('no such file', result['gzip_error'].lower())

    @patch('subprocess.check_output')
    def test_validate_gzip_format_valid_s3(self, mock_check_output):
        """Test validation of a valid S3 gzip file"""
        # Mock successful responses for both magic number check and header validation
        mock_check_output.side_effect = [
            b'\x1f\x8b',  # Valid magic number
            b'valid'      # Successful gunzip
        ]
        
        result = validate_gzip_format('s3://bucket/valid.gz')
        self.assertEqual(result, {}, "Valid S3 gzip file should return empty error dict")
        
        # Verify correct AWS commands were called
        calls = mock_check_output.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertIn('--range 0-1', str(calls[0]))
        self.assertIn('--range 0-9', str(calls[1]))

    @patch('subprocess.check_output')
    def test_validate_gzip_format_invalid_magic_number_s3(self, mock_check_output):
        """Test validation of an S3 file with invalid gzip magic number"""
        # Mock invalid magic number response
        mock_check_output.return_value = b'XX'
        
        result = validate_gzip_format('s3://bucket/invalid.gz')
        self.assertIn('gzip_error', result)
        self.assertIn('magic number', result['gzip_error'].lower())
        
        # Verify only magic number check was called
        mock_check_output.assert_called_once()
        self.assertIn('--range 0-1', str(mock_check_output.call_args))

    @patch('subprocess.check_output')
    def test_validate_gzip_format_invalid_header_s3(self, mock_check_output):
        """Test validation of an S3 file with invalid gzip header"""
        # Mock valid magic number but failed gunzip
        mock_check_output.side_effect = [
            b'\x1f\x8b',  # Valid magic number
            subprocess.CalledProcessError(1, 'cmd', stderr=b'not in gzip format')  # Failed gunzip
        ]
        
        result = validate_gzip_format('s3://bucket/invalid.gz')
        self.assertIn('gzip_error', result)
        self.assertIn('header', result['gzip_error'].lower())

    @patch('subprocess.check_output')
    def test_validate_gzip_format_s3_error(self, mock_check_output):
        """Test validation when S3 access fails"""
        # Mock S3 access error
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, 'cmd', stderr=b'The specified key does not exist')
        
        result = validate_gzip_format('s3://bucket/nonexistent.gz')
        self.assertIn('gzip_error', result)
        self.assertIn('header structure', result['gzip_error'].lower())

if __name__ == '__main__':
    unittest.main()
