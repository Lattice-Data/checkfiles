"""
Comprehensive tests for HDF5 file validation functionality.

This module tests the HDF5 validator including:
1. Core validation of HDF5 files
2. Stream handling (seekable and non-seekable)
3. Temporary file creation and management
4. Error handling
5. Integration with validation workflow
"""

import os
import pytest
import unittest
import tempfile
import io
import h5py
import numpy as np
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from src.validators.hdf5 import Hdf5Validator
from src.utils.helpers import download_s3_file_to_scratch
from src.core.validation import download_and_validate_random_access_file


@pytest.fixture
def validator():
    """
    Create an HDF5 validator instance for testing.
    
    Returns:
        Hdf5Validator: An initialized HDF5 validator
    """
    return Hdf5Validator()


@pytest.fixture
def test_hdf5_file():
    """
    Create a temporary HDF5 file for testing.
    
    Returns:
        str: Path to the temporary HDF5 file
    """
    # Skip if h5py is not available
    try:
        import h5py
    except ImportError:
        pytest.skip("h5py not installed, skipping HDF5 tests")
    
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as temp_file:
        temp_path = temp_file.name
    
    # Create a simple HDF5 file with some test data
    with h5py.File(temp_path, 'w') as f:
        # Create a group
        grp = f.create_group("test_group")
        
        # Create datasets
        f.create_dataset("dataset1", data=np.arange(10))
        grp.create_dataset("nested_dataset", data=np.random.rand(5, 5))
        
        # Add attributes
        f.attrs["file_attribute"] = "test"
        grp.attrs["group_attribute"] = 42
    
    yield temp_path
    
    # Clean up the test file
    try:
        os.unlink(temp_path)
    except:
        pass


class TestHdf5ValidationCore(unittest.TestCase):
    """Test class for core HDF5 validation functionality using unittest style."""
    
    def setUp(self):
        """Set up test environment."""
        self.validator = Hdf5Validator()
        # Create a test temp directory to use as scratch space
        self.temp_dir = tempfile.mkdtemp()
        self.old_scratch_dir = os.environ.get('SCRATCH_DIR')
        os.environ['SCRATCH_DIR'] = self.temp_dir
    
    def tearDown(self):
        """Clean up test environment."""
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
    
    def test_validator_initialization(self):
        """Test the HDF5 validator is properly initialized."""
        self.assertIsInstance(self.validator, Hdf5Validator)
    
    def test_stream_seekable_detection(self):
        """Test detection of seekable streams."""
        # Test with seekable stream (BytesIO)
        seekable_stream = io.BytesIO(b"test data")
        self.assertTrue(self.validator.is_stream_seekable(seekable_stream))
        
        # Test with non-seekable stream (mock without seek/tell)
        non_seekable_stream = MagicMock(spec=io.BytesIO)
        del non_seekable_stream.seek
        del non_seekable_stream.tell
        self.assertFalse(self.validator.is_stream_seekable(non_seekable_stream))
    
    @patch('src.validators.hdf5.H5PY_AVAILABLE', True)
    @patch('src.validators.hdf5.os.path.exists')
    @patch('src.validators.hdf5.tempfile.mkstemp')
    @patch('src.validators.hdf5.os.close')
    @patch('builtins.open')
    @patch('src.validators.hdf5.shutil.copyfileobj')
    def test_create_temp_file_from_stream(self, mock_copyfileobj, mock_open, 
                                       mock_close, mock_mkstemp, mock_exists):
        """Test creation of temporary file from stream."""
        # Setup mocks
        mock_exists.return_value = True
        mock_mkstemp.return_value = (123, os.path.join(self.temp_dir, 'test_temp_file.h5'))
        
        # Mock file object
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock input stream
        input_stream = MagicMock()
        
        # Call the method
        temp_path, file_obj = self.validator.create_temp_file_from_stream(input_stream, is_gzipped=False)
        
        # Verify results
        self.assertTrue(temp_path.startswith(self.temp_dir))  # Should use scratch dir
        mock_exists.assert_called_with(self.temp_dir)
        mock_mkstemp.assert_called_once()
        mock_close.assert_called_once()
        mock_open.assert_called()
        mock_copyfileobj.assert_called_once()
    
    @patch('src.validators.hdf5.H5PY_AVAILABLE', True)
    @patch('src.validators.hdf5.h5py.File')
    def test_validate_stream_with_seekable_stream(self, mock_h5py_file):
        """Test validating a seekable stream."""
        # Mock h5py File and groups/datasets counting
        mock_file = MagicMock()
        mock_h5py_file.return_value.__enter__.return_value = mock_file
        
        # Mock the counting methods
        with patch.object(self.validator, '_count_groups', return_value=5):
            with patch.object(self.validator, '_count_datasets', return_value=10):
                with patch.object(self.validator, '_count_attributes', return_value=20):
                    # Create a seekable stream
                    stream = io.BytesIO(b"test data")
                    
                    # Call the validate_stream method
                    result = self.validator.validate_stream(stream, is_gzipped=False)
                    
                    # Verify results
                    self.assertTrue(result['valid'])
                    self.assertEqual(result['stats']['groups'], 5)
                    self.assertEqual(result['stats']['datasets'], 10)
                    self.assertEqual(result['stats']['attributes'], 20)
                    
                    # Verify h5py.File was called
                    mock_h5py_file.assert_called_once()
    
    @patch('src.validators.hdf5.H5PY_AVAILABLE', True)
    @patch('src.validators.hdf5.Hdf5Validator.create_temp_file_from_stream')
    @patch('src.validators.hdf5.h5py.File')
    def test_validate_stream_with_non_seekable_stream(self, mock_h5py_file, mock_create_temp):
        """Test validating a non-seekable stream."""
        # Mock temporary file creation
        mock_temp_file = MagicMock()
        mock_temp_path = '/tmp/temp_file.h5'
        mock_create_temp.return_value = (mock_temp_path, mock_temp_file)
        
        # Mock h5py File and groups/datasets counting
        mock_file = MagicMock()
        mock_h5py_file.return_value.__enter__.return_value = mock_file
        
        # Mock is_stream_seekable to return False
        with patch.object(self.validator, 'is_stream_seekable', return_value=False):
            # Mock the counting methods
            with patch.object(self.validator, '_count_groups', return_value=5):
                with patch.object(self.validator, '_count_datasets', return_value=10):
                    with patch.object(self.validator, '_count_attributes', return_value=20):
                        # Mock non-seekable stream
                        stream = MagicMock()
                        
                        # Call the validate_stream method
                        result = self.validator.validate_stream(stream, is_gzipped=False)
                        
                        # Verify results
                        self.assertTrue(result['valid'])
                        self.assertEqual(result['stats']['groups'], 5)
                        self.assertEqual(result['stats']['datasets'], 10)
                        self.assertEqual(result['stats']['attributes'], 20)
                        
                        # Verify temp file creation was called
                        mock_create_temp.assert_called_once_with(stream, False)
                        
                        # Verify h5py.File was called with the temp file
                        mock_h5py_file.assert_called_once()
    
    @patch('src.validators.hdf5.H5PY_AVAILABLE', True)
    @patch('src.validators.hdf5.h5py.File', side_effect=Exception("HDF5 validation error"))
    def test_validation_error_handling(self, mock_h5py_file):
        """Test handling of validation errors."""
        # Create a seekable stream
        stream = io.BytesIO(b"invalid data")
        
        # Call the validate_stream method with invalid data
        result = self.validator.validate_stream(stream, is_gzipped=False)
        
        # Verify results
        self.assertFalse(result['valid'])
        self.assertIn('validation_error', result['errors'])
        self.assertIn('HDF5 validation error', result['errors']['validation_error'])
    
    @patch('src.validators.hdf5.H5PY_AVAILABLE', False)
    def test_validation_without_h5py(self):
        """Test validation behavior when h5py is not available."""
        # Create a new validator instance for this test to ensure H5PY_AVAILABLE is used
        with patch('src.validators.hdf5.H5PY_AVAILABLE', False, create=True):
            validator = Hdf5Validator()
            
            # Direct patch of has_h5py attribute
            validator.has_h5py = False
            
            stream = io.BytesIO(b"test data")
            
            result = validator.validate_stream(stream, is_gzipped=False)
            
            # When h5py is not available, it should return valid=True with a warning
            self.assertTrue(result['valid'])
            self.assertIn('h5py_missing', result['warnings'])


# PyTest-style tests for file-level validation
def test_validate_file_valid(validator, test_hdf5_file):
    """Test validating a valid HDF5 file."""
    result = validator.validate_file(test_hdf5_file)
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0
    
    # Verify statistics
    stats = result["stats"]
    assert stats["groups"] > 0  # Should be at least 1 group (test_group)
    assert stats["datasets"] > 0  # Should be at least 2 datasets
    assert stats["attributes"] > 0  # Should be at least 2 attributes


def test_validate_file_not_found(validator):
    """Test validating a non-existent file."""
    result = validator.validate_file("/path/to/nonexistent/file.h5")
    
    assert result["valid"] is False
    assert "file_not_found" in result["errors"]


def test_validate_empty_file(validator):
    """Test validating an empty HDF5 file."""
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # Don't write anything to the file
        
        result = validator.validate_file(temp_path)
        
        assert result["valid"] is False
        # The error now comes from h5py trying to read the empty file stream
        assert "validation_error" in result["errors"], "Expected validation error for empty file"
        assert "file signature not found" in result["errors"]["validation_error"], "Expected specific h5py error for empty file"
    finally:
        # Clean up
        try:
            os.unlink(temp_path)
        except:
            pass


def test_validate_invalid_file(validator):
    """Test validating an invalid HDF5 file."""
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as temp_file:
        temp_path = temp_file.name
        
        # Write some random data that is not a valid HDF5 file
        temp_file.write(b"This is not a valid HDF5 file")
    
    try:
        result = validator.validate_file(temp_path)
        
        assert result["valid"] is False
        # Updated error message check for new format
        assert "validation_error" in result["errors"]
        assert "Invalid HDF5 structure" in result["errors"]["validation_error"] 
        assert "file signature not found" in result["errors"]["validation_error"] # More specific h5py error
    finally:
        # Clean up
        try:
            os.unlink(temp_path)
        except:
            pass


# Integration tests for random access validation
class TestHdf5Integration(unittest.TestCase):
    """Test class for HDF5 integration with validation workflow."""

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
            path, status = download_s3_file_to_scratch('s3://bucket/file.h5', 'h5')
            
            # Check if the helper function was called correctly
            mock_run.assert_called_once()
            self.assertIn('aws s3 cp s3://bucket/file.h5', mock_run.call_args[0][0])
            
            # Check if function returns expected results
            self.assertTrue(status['success'])
            self.assertEqual(status['original_s3_path'], 's3://bucket/file.h5')
            self.assertTrue(path.startswith(self.temp_dir))
            self.assertTrue('h5_' in path)

    @patch('src.utils.helpers.subprocess.run')
    def test_download_failure(self, mock_run):
        """Test handling of download failures."""
        # Mock subprocess failed run
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Access denied"
        mock_run.return_value = mock_result
        
        path, status = download_s3_file_to_scratch('s3://bucket/file.h5', 'h5')
        
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
        mock_download.return_value = ('/tmp/temp_file.h5', {'success': True})
        
        # Mock hash calculation
        mock_calculate_hashes.return_value = {'md5sum': 'abc123', 'file_size': 1000}
        
        # Mock local file validation
        mock_validate_local.return_value = {
            'file_path': '/tmp/temp_file.h5',
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
                's3://bucket/file.h5',
                'h5',
                debug=False
            )
        
        # Verify results
        self.assertTrue(result['success'])
        self.assertEqual(result['file_path'], 's3://bucket/file.h5')  # Should use original S3 path
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
            's3://bucket/file.h5',
            'h5',
            debug=False
        )
        
        # Verify error handling
        self.assertFalse(result['success'])
        self.assertEqual(result['file_path'], 's3://bucket/file.h5')
        self.assertIn('Download failed', result['error'])


if __name__ == '__main__':
    unittest.main() 