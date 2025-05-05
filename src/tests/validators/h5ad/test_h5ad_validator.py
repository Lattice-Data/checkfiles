"""
Comprehensive tests for H5AD file validation functionality.

This module tests the H5AD validator including:
1. Core validation of H5AD files
2. Feature type handling
3. Genome information extraction
4. Stream handling (seekable and non-seekable)
5. Error handling
"""

import os
import sys
import tempfile
import pytest
import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock, PropertyMock
from io import BytesIO

# Try to import scanpy and anndata
try:
    import scanpy as sc
    import anndata as ad
    SCANPY_AVAILABLE = True
except ImportError:
    SCANPY_AVAILABLE = False

from src.validators.h5ad import H5adValidator
from src.validators.hdf5 import Hdf5Validator


@pytest.fixture
def validator():
    """Create an H5AD validator instance."""
    return H5adValidator()


def create_test_h5ad(filename, with_errors=False):
    """Create a test H5AD file with optional errors.
    
    Args:
        filename: The filename to write to
        with_errors: Whether to include validation errors
        
    Returns:
        Path to the created file
    """
    # Skip if scanpy is not available
    if not SCANPY_AVAILABLE:
        pytest.skip("scanpy not available")
        
    # Create a simple AnnData object
    n_obs = 10  # 10 cells
    n_vars = 15  # 15 genes
    
    # Create observation data (cells)
    obs_names = [f"CELL_{i}" for i in range(n_obs)]
    if with_errors:
        # Add problematic cell names
        obs_names[0] = "CELL_0.1"  # Add a cell with .1 suffix
        
    # Create variable data (genes)
    var_names = [f"GENE_{i}" for i in range(n_vars)]
    if with_errors:
        # Add a date-formatted symbol
        var_names[0] = "Mar-1"
        
    # Create the expression matrix
    X = np.random.normal(size=(n_obs, n_vars))
    
    # Create observation and variable dataframes
    obs = pd.DataFrame(index=obs_names)
    var = pd.DataFrame(index=var_names)
    
    # Add feature_types column to var
    feature_types = ['Gene Expression'] * n_vars
    if with_errors:
        # Add an invalid feature type
        feature_types[1] = 'Invalid Type'
        
    var['feature_types'] = feature_types
    
    # Add gene_ids column to var with Ensembl IDs
    gene_ids = [f"ENSG{str(i).zfill(11)}" for i in range(n_vars)]
    if with_errors:
        # Add a gene ID with a version
        gene_ids[2] = "ENSG00000000003.14"
        # Add a non-ENSG ID
        gene_ids[3] = "NON_ENSG_ID"
        
    var['gene_ids'] = gene_ids
    
    # Add gene_versions column if not with_errors
    if not with_errors:
        var['gene_versions'] = [f"ENSG{str(i).zfill(11)}.1" for i in range(n_vars)]
    else:
        # Add gene_versions with one missing a version
        gene_versions = [f"ENSG{str(i).zfill(11)}.1" for i in range(n_vars)]
        gene_versions[4] = "ENSG00000000004"  # Missing version
        var['gene_versions'] = gene_versions
        
    # Add a PAR_Y gene
    if with_errors:
        # Add a PAR_Y gene with inconsistent formatting
        gene_ids[5] = "ENSG00000000005_PARY"  # Missing underscore
        var.loc[var.index[5], 'gene_versions'] = "ENSG00000000005.1_PAR_Y"
    else:
        # Add a properly formatted PAR_Y gene
        gene_ids[5] = "ENSG00000000005_PAR_Y"
        var.loc[var.index[5], 'gene_versions'] = "ENSG00000000005.1_PAR_Y"
        
    # Add genome column
    var['genome'] = ['GRCh38'] * n_vars
        
    # Create the AnnData object
    adata = ad.AnnData(X=X, obs=obs, var=var)
    
    # Save to file
    adata.write_h5ad(filename)
    
    return filename


# PyTest-style tests with mocked file creation
@pytest.mark.skipif(not SCANPY_AVAILABLE, reason="scanpy not available")
@patch('src.validators.h5ad.sc.read_h5ad')
def test_valid_h5ad(mock_read_h5ad, validator):
    """Test validation of a valid H5AD file with mocking."""
    # Create mock AnnData object
    mock_adata = MagicMock()
    
    # Mock var dataframe with necessary columns
    var_data = {
        'feature_types': ['Gene Expression'] * 10,
        'gene_ids': [f"ENSG{str(i).zfill(11)}" for i in range(10)],
        'gene_versions': [f"ENSG{str(i).zfill(11)}.1" for i in range(10)],
        'genome': ['GRCh38'] * 10
    }
    var_df = pd.DataFrame(var_data)
    mock_adata.var = var_df
    
    # Mock observation names and shape
    mock_adata.obs_names = [f"CELL_{i}" for i in range(10)]
    mock_adata.shape = (10, 10)
    
    # Set the return value for sc.read_h5ad
    mock_read_h5ad.return_value = mock_adata
    
    # Create a dummy BytesIO to pass to validate_stream
    stream = BytesIO(b"mocked h5ad file data")
    
    # Call validate_stream with the mock
    result = validator.validate_stream(stream, is_gzipped=False)
    
    # Verify the file was "validated"
    assert result['valid'] is True
    assert 'errors' in result
    assert len(result['errors']) == 0
    assert 'stats' in result
    assert 'observation_count' in result['stats']
    assert result['stats']['observation_count'] == 10
    assert 'genomes' in result['stats']
    assert result['stats']['genomes'] == ['GRCh38']
    assert 'feature_counts' in result['stats']


@pytest.mark.skipif(not SCANPY_AVAILABLE, reason="scanpy not available")
@patch('src.validators.h5ad.sc.read_h5ad')
def test_invalid_h5ad(mock_read_h5ad, validator):
    """Test validation of an invalid H5AD file with mocking."""
    # Create mock AnnData object with validation errors
    mock_adata = MagicMock()
    
    # Mock var dataframe with validation errors
    var_data = {
        'feature_types': ['Gene Expression'] * 9 + ['Invalid Type'],
        'gene_ids': [f"ENSG{str(i).zfill(11)}" for i in range(8)] + 
                   ["ENSG00000000008.14", "NON_ENSG_ID"],  # Add invalid IDs
        'gene_versions': [f"ENSG{str(i).zfill(11)}.1" for i in range(9)] + 
                        ["ENSG00000000009"],  # Missing version
        'genome': ['GRCh38'] * 10
    }
    var_df = pd.DataFrame(var_data)
    mock_adata.var = var_df
    
    # Mock observation names with a problematic cell name
    mock_adata.obs_names = ["CELL_0.1"] + [f"CELL_{i}" for i in range(1, 10)]
    mock_adata.shape = (10, 10)
    
    # Set index with date-formatted symbol
    var_df.index = ["Mar-1"] + [f"GENE_{i}" for i in range(1, 10)]
    
    # Set the return value for sc.read_h5ad
    mock_read_h5ad.return_value = mock_adata
    
    # Create a dummy BytesIO to pass to validate_stream
    stream = BytesIO(b"mocked h5ad file data with errors")
    
    # Call validate_stream with the mock
    result = validator.validate_stream(stream, is_gzipped=False)
    
    # Verify the validation errors were detected
    assert result['valid'] is False
    assert 'errors' in result
    assert len(result['errors']) > 0
    
    # Check for specific errors
    assert 'var.feature_types[Invalid Type]' in result['errors']
    assert any('ENSG format' in key for key in result['errors'].keys())
    assert any('ENSG.N format' in key for key in result['errors'].keys())
    assert 'cell_id suffix' in result['errors']
    assert 'date-formatted symbols' in result['errors']


@pytest.mark.skipif(not SCANPY_AVAILABLE, reason="scanpy not available")
@patch('src.validators.h5ad.sc.read_h5ad')
def test_h5ad_with_missing_columns(mock_read_h5ad, validator):
    """Test validation of an H5AD file with missing required columns."""
    # Create mock AnnData object without required columns
    mock_adata = MagicMock()
    
    # Mock var dataframe WITHOUT feature_types and gene_ids
    var_data = {}  # Empty dataframe with no required columns
    var_df = pd.DataFrame(var_data)
    mock_adata.var = var_df
    
    # Mock observation names and shape
    mock_adata.obs_names = [f"CELL_{i}" for i in range(5)]
    mock_adata.shape = (5, 10)
    
    # Set the return value for sc.read_h5ad
    mock_read_h5ad.return_value = mock_adata
    
    # Create a dummy BytesIO to pass to validate_stream
    stream = BytesIO(b"mocked h5ad file data with missing columns")
    
    # Call validate_stream with the mock
    result = validator.validate_stream(stream, is_gzipped=False)
    
    # Verify the validation errors were detected
    assert result['valid'] is False
    assert 'errors' in result
    assert 'var.feature_types' in result['errors']
    assert 'var.gene_ids' in result['errors']


@pytest.mark.skipif(SCANPY_AVAILABLE, reason="scanpy is available")
def test_h5ad_without_scanpy(validator):
    """Test validation behavior when scanpy is not available."""
    # Create a mock stream
    stream = BytesIO(b'not a real h5ad file')
    
    # Create a mock validator
    mock_validator = H5adValidator()
    mock_validator.has_scanpy = False
    
    # Validate the stream
    result = mock_validator.validate_stream(stream, is_gzipped=False)
    
    # Check that we get a warning but no validation
    assert 'warnings' in result
    assert 'scanpy_missing' in result['warnings']
    assert result['valid'] is True  # We assume valid when we can't check


# Unittest-style tests
class TestH5adValidation(unittest.TestCase):
    """Test class for H5AD validation functionality using unittest style."""
    
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
    @patch('tempfile.mkstemp')
    @patch('os.close')
    @patch('os.path.exists')
    @patch('os.environ.get')
    @patch('builtins.open')
    @patch('shutil.copyfileobj')  # Mock shutil.copyfileobj directly
    def test_validate_stream_seekable_legacy(self, mock_copyfileobj, mock_open, mock_environ_get, 
                                     mock_path_exists, mock_os_close, mock_mkstemp, 
                                     mock_sc, mock_base_validate):
        """
        Legacy test for validation with a seekable stream.
        This test is kept for compatibility but adapted to the new implementation
        that always uses a temporary file.
        """
        # Mock base HDF5 validation to return valid result
        mock_base_validate.return_value = {
            'valid': True,
            'errors': {},
            'warnings': {},
            'stats': {}
        }
        
        # Mock the create_temp_file_from_stream method to avoid depending on its implementation
        with patch.object(self.validator, 'create_temp_file_from_stream') as mock_create_temp:
            # Set up a temp file
            mock_temp_file = MagicMock()
            mock_temp_path = '/tmp/test_h5ad_file.h5ad'
            mock_create_temp.return_value = (mock_temp_path, mock_temp_file)
            
            # Mock seekable stream - note that in new implementation, 
            # seekability doesn't matter as we always create a temp file
            seekable_stream = MagicMock()
            
            # Mock the _validate_h5ad_file method to return a simple valid result
            with patch.object(self.validator, '_validate_h5ad_file', return_value={
                'errors': {},
                'warnings': {},
                'stats': {'observation_count': 200}
            }):
                # Mock os.unlink to prevent file deletion attempts
                with patch('os.unlink'):
                    result = self.validator.validate_stream(seekable_stream, is_gzipped=False)
            
            # Verify the temp file was created (always happens now)
            mock_create_temp.assert_called_once_with(seekable_stream, False)
            
            # Verify the result is valid
            self.assertTrue(result['valid'])
            self.assertEqual(result['stats'].get('observation_count'), 200)
    
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
        
        # Mock the create_temp_file_from_stream method with a real temp file
        with tempfile.NamedTemporaryFile(suffix='.h5ad', delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(b"test h5ad data")
        
        try:
            # Create a test-specific patch for create_temp_file_from_stream
            with patch.object(self.validator, 'create_temp_file_from_stream') as mock_create_temp:
                # Set up the mock to return a test file
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
                    
                    # Close the mock file
                    mock_temp_file.close()
        finally:
            # Clean up
            try:
                os.unlink(temp_path)
            except:
                pass

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