"""
Tests for H5AD file validation functionality.

This module tests the validation of H5AD files with specific focus
on handling the random access requirements.
"""

import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock, PropertyMock
import io

# Add project root to path to avoid circular imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from src.validators.h5ad import H5adValidator
from src.validators.hdf5 import Hdf5Validator


class TestH5adValidation(unittest.TestCase):
    """Test class for H5AD validation functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.validator = H5adValidator()
        
    def tearDown(self):
        """Clean up after tests."""
        pass
        
    def test_validator_initialization(self):
        """Test the H5AD validator is properly initialized."""
        self.assertIsInstance(self.validator, H5adValidator)
        self.assertIsInstance(self.validator, Hdf5Validator)  # Should inherit from Hdf5Validator
    
    @patch('src.validators.h5ad.H5PY_AVAILABLE', True)
    @patch('src.validators.h5ad.SCANPY_AVAILABLE', True)
    @patch('src.validators.hdf5.Hdf5Validator.validate_stream')
    @patch('src.validators.h5ad.H5adValidator.create_temp_file_from_stream')
    @patch('src.validators.h5ad.sc')
    def test_validate_stream_creates_temp_file_for_non_seekable(self, mock_sc, mock_create_temp, mock_base_validate):
        """Test that a temporary file is created for non-seekable streams."""
        # Mock base HDF5 validation to return valid result
        mock_base_validate.return_value = {
            'valid': True,
            'errors': {},
            'warnings': {},
            'stats': {}
        }
        
        # Mock a non-seekable stream
        non_seekable_stream = MagicMock()
        
        # Make is_stream_seekable return False
        with patch.object(self.validator, 'is_stream_seekable', return_value=False):
            # Mock the temp file creation
            mock_temp_file = MagicMock()
            mock_temp_path = '/tmp/test_h5ad_file.h5ad'
            mock_create_temp.return_value = (mock_temp_path, mock_temp_file)
            
            # Mock the _validate_h5ad_file method to return a simple valid result
            with patch.object(self.validator, '_validate_h5ad_file', return_value={
                'errors': {},
                'warnings': {},
                'stats': {'observation_count': 100}
            }):
                result = self.validator.validate_stream(non_seekable_stream, is_gzipped=False)
            
            # Verify temp file was created for non-seekable stream
            mock_create_temp.assert_called_once_with(non_seekable_stream, False)
            
            # Verify the result is valid
            self.assertTrue(result['valid'])
            self.assertEqual(result['stats'].get('observation_count'), 100)
    
    @patch('src.validators.h5ad.H5PY_AVAILABLE', True)
    @patch('src.validators.h5ad.SCANPY_AVAILABLE', True)
    @patch('src.validators.hdf5.Hdf5Validator.validate_stream')
    @patch('src.validators.h5ad.sc')
    def test_validate_stream_with_temp_file(self, mock_sc, mock_base_validate):
        """Test validation with a temporary file."""
        # Mock base HDF5 validation to return valid result
        mock_base_validate.return_value = {
            'valid': True,
            'errors': {},
            'warnings': {},
            'stats': {}
        }
        
        # Mock the stream
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"test data"
        
        # Mock the create_temp_file_from_stream method to avoid depending on its implementation
        with patch.object(self.validator, 'create_temp_file_from_stream') as mock_create_temp:
            # Set up a temp file
            with tempfile.NamedTemporaryFile(suffix='.h5ad', delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(b"test h5ad data")
                temp_file.flush()
            
            # Return our prepared temp file
            mock_temp_file = open(temp_path, 'rb')
            mock_create_temp.return_value = (temp_path, mock_temp_file)
            
            # Mock the _validate_h5ad_file method
            with patch.object(self.validator, '_validate_h5ad_file', return_value={
                'errors': {},
                'warnings': {},
                'stats': {'observation_count': 200}
            }):
                # Run the validation
                result = self.validator.validate_stream(mock_stream, is_gzipped=False)
                
                # Verify the result is valid
                self.assertTrue(result['valid'])
                self.assertEqual(result['stats'].get('observation_count'), 200)
                
                # Verify the temp file was created
                mock_create_temp.assert_called_once_with(mock_stream, False)
            
            # Close mock_temp_file
            mock_temp_file.close()
            
            # Clean up
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def test_validates_feature_types(self):
        """Test validation of feature types."""
        # Mock AnnData object
        mock_adata = MagicMock()
        
        # Mock var dataframe with feature_types
        mock_adata.var = MagicMock()
        mock_adata.var.columns = ['feature_types']
        
        # Mock value_counts method
        value_counts_result = MagicMock()
        value_counts_result.to_dict.return_value = {
            'Gene Expression': 1000, 
            'Peaks': 500,
            'Antibody Capture': 200
        }
        mock_adata.var.__getitem__.return_value.value_counts.return_value = value_counts_result
        
        # Call the method directly
        errors = {}
        stats = {}
        self.validator._validate_feature_types(mock_adata, errors, stats)
        
        # Verify results
        self.assertEqual(len(errors), 0)  # No errors expected
        self.assertIn('feature_counts', stats)
        self.assertEqual(len(stats['feature_counts']), 3)  # Three feature types
        
        # Verify feature type mapping
        feature_types = {item['feature_type'] for item in stats['feature_counts']}
        self.assertSetEqual(feature_types, {'gene', 'peak', 'antibody capture'})

    @patch('src.validators.hdf5.Hdf5Validator.validate_stream')
    def test_h5ad_validation_error_handling(self, mock_base_validate):
        """Test handling of validation errors in H5AD files."""
        # Mock base HDF5 validation to return valid result
        mock_base_validate.return_value = {
            'valid': True,
            'errors': {},
            'warnings': {},
            'stats': {}
        }
        
        # Mock a non-seekable stream
        non_seekable_stream = MagicMock()
        
        # Make is_stream_seekable return False
        with patch.object(self.validator, 'is_stream_seekable', return_value=False):
            # Simulate error in create_temp_file_from_stream
            with patch.object(self.validator, 'create_temp_file_from_stream', 
                            side_effect=RuntimeError("Temp file creation error")):
                result = self.validator.validate_stream(non_seekable_stream, is_gzipped=False)
                
                # Verify the error is captured
                self.assertFalse(result['valid'])
                self.assertIn('h5ad_validation_error', result['errors'])
                self.assertIn('Temp file creation error', result['errors']['h5ad_validation_error'])

    def test_validate_h5ad_file_error_handling(self):
        """Test handling of file reading errors in _validate_h5ad_file."""
        # Mock scanpy raising an exception when reading file
        with patch('src.validators.h5ad.sc.read_h5ad', side_effect=ValueError("Invalid H5AD file")):
            result = self.validator._validate_h5ad_file('/fake/path/to/file.h5ad')
            
            # Verify the error is captured
            self.assertIn('file_reading_error', result['errors'])
            self.assertIn('Invalid H5AD file', result['errors']['file_reading_error'])


if __name__ == '__main__':
    unittest.main() 