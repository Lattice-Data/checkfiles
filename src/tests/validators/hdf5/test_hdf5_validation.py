"""
Tests for HDF5 and H5AD file validation functionality.

This module tests the special handling of HDF5 and H5AD files,
which require random access and can't be validated via streaming.
"""

import os
import unittest
import tempfile
from unittest.mock import patch, MagicMock
import io

from src.core.validation import download_and_validate_random_access_file
from src.utils.helpers import download_s3_file_to_scratch
from src.validators.hdf5 import Hdf5Validator
from src.validators.h5ad import H5adValidator


class TestHdf5Validation(unittest.TestCase):
    """Test class for HDF5 validation functionality."""

    def setUp(self):
        """Set up test environment."""
        # Create a temp directory for scratch space
        self.temp_dir = tempfile.mkdtemp()
        self.old_scratch_dir = os.environ.get('SCRATCH_DIR')
        os.environ['SCRATCH_DIR'] = self.temp_dir

    def tearDown(self):
        """Clean up after tests."""
        # Restore original environment variable
        if self.old_scratch_dir:
            os.environ['SCRATCH_DIR'] = self.old_scratch_dir
        else:
            os.environ.pop('SCRATCH_DIR', None)
        
        # Clean up temp directory
        try:
            os.rmdir(self.temp_dir)
        except OSError:
            # Directory might not be empty if tests failed and left files
            pass

    @patch('src.utils.helpers.subprocess.run')
    def test_download_s3_file_to_scratch(self, mock_run):
        """Test downloading a file from S3 to scratch directory."""
        # Mock subprocess successful run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            path, status = download_s3_file_to_scratch('s3://bucket/file.h5ad', 'h5ad')
            
            # Check if the helper function was called correctly
            mock_run.assert_called_once()
            self.assertIn('aws s3 cp s3://bucket/file.h5ad', mock_run.call_args[0][0])
            
            # Check if function returns expected results
            self.assertTrue(status['success'])
            self.assertEqual(status['original_s3_path'], 's3://bucket/file.h5ad')
            self.assertTrue(path.startswith(self.temp_dir))
            self.assertTrue('h5ad_' in path)

    @patch('src.utils.helpers.subprocess.run')
    def test_download_failure(self, mock_run):
        """Test handling of download failures."""
        # Mock subprocess failed run
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Access denied"
        mock_run.return_value = mock_result
        
        path, status = download_s3_file_to_scratch('s3://bucket/file.h5ad', 'h5ad')
        
        # Check error handling
        self.assertFalse(status['success'])
        self.assertIn('Failed to download', status['error'])
        self.assertIsNone(path)

    @patch('src.core.validation.download_s3_file_to_scratch')
    @patch('src.core.validation.validate_local_file')
    @patch('src.core.validation.calculate_hashes_for_stream')
    def test_download_and_validate_random_access_file(self, mock_calculate_hashes, 
                                                     mock_validate_local, mock_download):
        """Test the download and validation process for random access files."""
        # Mock the download helper
        mock_download.return_value = ('/tmp/temp_file.h5ad', {'success': True})
        
        # Mock hash calculation
        mock_calculate_hashes.return_value = {'md5sum': 'abc123', 'file_size': 1000}
        
        # Mock local file validation
        mock_validate_local.return_value = {
            'file_path': '/tmp/temp_file.h5ad',
            'success': True,
            'results': {
                'valid': True,
                'stats': {'groups': 5, 'datasets': 10}
            }
        }
        
        # Mock file operations
        mock_open = MagicMock()
        with patch('builtins.open', mock_open):
            result = download_and_validate_random_access_file(
                's3://bucket/file.h5ad',
                'h5ad',
                debug=False
            )
        
        # Verify results
        self.assertTrue(result['success'])
        self.assertEqual(result['file_path'], 's3://bucket/file.h5ad')  # Should use original S3 path
        self.assertTrue(result['results']['valid'])
        
        # Check if hashes were merged correctly
        self.assertEqual(result['results']['stats']['md5sum'], 'abc123')
        self.assertEqual(result['results']['stats']['groups'], 5)

    @patch('src.core.validation.download_s3_file_to_scratch')
    def test_download_failure_handling(self, mock_download):
        """Test handling of download failures in the validation function."""
        # Mock failed download
        mock_download.return_value = (None, {
            'success': False, 
            'error': 'Download failed'
        })
        
        result = download_and_validate_random_access_file(
            's3://bucket/file.h5ad',
            'h5ad',
            debug=False
        )
        
        # Verify error handling
        self.assertFalse(result['success'])
        self.assertEqual(result['file_path'], 's3://bucket/file.h5ad')
        self.assertIn('Download failed', result['error'])

    def test_hdf5_validator_recognizes_random_access_requirement(self):
        """Test HDF5 validator correctly identifies the need for random access."""
        validator = Hdf5Validator()
        
        # Test with non-seekable stream
        non_seekable_stream = MagicMock(spec=io.BytesIO)
        # Remove seek and tell attributes to make it non-seekable
        del non_seekable_stream.seek
        del non_seekable_stream.tell
        
        self.assertFalse(validator.is_stream_seekable(non_seekable_stream))
        
        # Test with seekable stream
        seekable_stream = io.BytesIO(b'test data')
        self.assertTrue(validator.is_stream_seekable(seekable_stream))

    def test_h5ad_validator_inherits_random_access_handling(self):
        """Test H5AD validator inherits the random access handling from HDF5 validator."""
        validator = H5adValidator()
        
        # Verify inheritance of seekable detection
        seekable_stream = io.BytesIO(b'test data')
        self.assertTrue(validator.is_stream_seekable(seekable_stream))
        
        # Verify temp file creation method is available
        self.assertTrue(hasattr(validator, 'create_temp_file_from_stream'))


if __name__ == '__main__':
    unittest.main() 