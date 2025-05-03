"""
Tests for core HDF5 validation functionality.

This module tests the basic HDF5 validator functionality, focusing on:
1. Stream handling
2. Temporary file creation
3. Error handling
"""

import os
import unittest
import tempfile
from unittest.mock import patch, MagicMock, PropertyMock
import io

from src.validators.hdf5 import Hdf5Validator


class TestHdf5ValidationCore(unittest.TestCase):
    """Test class for core HDF5 validation functionality."""
    
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


if __name__ == '__main__':
    unittest.main() 