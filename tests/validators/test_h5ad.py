"""
Unit tests for the H5AD validator.
"""

import os
import pytest
import tempfile
import numpy as np
import pandas as pd
from io import BytesIO

try:
    import scanpy as sc
    import anndata as ad
    SCANPY_AVAILABLE = True
except ImportError:
    SCANPY_AVAILABLE = False

from src.validators.h5ad import H5adValidator

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

@pytest.mark.skipif(not SCANPY_AVAILABLE, reason="scanpy not available")
def test_valid_h5ad(validator):
    """Test validation of a valid H5AD file."""
    with tempfile.NamedTemporaryFile(suffix='.h5ad', delete=False) as tmp:
        try:
            # Create a valid H5AD file
            filename = create_test_h5ad(tmp.name)
            
            # Read the file into a BytesIO for the validator
            with open(filename, 'rb') as f:
                file_data = f.read()
            
            # Create a BytesIO object for validation
            stream = BytesIO(file_data)
            
            # Validate the file
            result = validator.validate_stream(stream, is_gzipped=False)
            
            # Check the result
            assert result['valid'] is True
            assert 'errors' in result
            assert len(result['errors']) == 0
            assert 'stats' in result
            assert 'observation_count' in result['stats']
            assert result['stats']['observation_count'] == 10
            assert 'genomes' in result['stats']
            assert result['stats']['genomes'] == ['GRCh38']
            assert 'feature_counts' in result['stats']
            
        finally:
            # Clean up
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

@pytest.mark.skipif(not SCANPY_AVAILABLE, reason="scanpy not available")
def test_invalid_h5ad(validator):
    """Test validation of an invalid H5AD file."""
    with tempfile.NamedTemporaryFile(suffix='.h5ad', delete=False) as tmp:
        try:
            # Create an H5AD file with errors
            filename = create_test_h5ad(tmp.name, with_errors=True)
            
            # Read the file into a BytesIO for the validator
            with open(filename, 'rb') as f:
                file_data = f.read()
            
            # Create a BytesIO object for validation
            stream = BytesIO(file_data)
            
            # Validate the file
            result = validator.validate_stream(stream, is_gzipped=False)
            
            # Check the result
            assert result['valid'] is False
            assert 'errors' in result
            assert len(result['errors']) > 0
            
            # Check for specific errors
            assert 'var.feature_types[Invalid Type]' in result['errors']
            assert 'ENSG format' in result['errors']
            assert 'var.gene_ids' in result['errors']
            assert 'ENSG.N format' in result['errors']
            assert 'cell_id suffix' in result['errors']
            assert 'date-formatted symbols' in result['errors']
            
        finally:
            # Clean up
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

@pytest.mark.skipif(not SCANPY_AVAILABLE, reason="scanpy not available")
def test_h5ad_with_missing_columns(validator):
    """Test validation of an H5AD file with missing required columns."""
    with tempfile.NamedTemporaryFile(suffix='.h5ad', delete=False) as tmp:
        try:
            # Create a simple AnnData object without required columns
            n_obs = 5
            n_vars = 10
            X = np.random.normal(size=(n_obs, n_vars))
            obs = pd.DataFrame(index=[f"CELL_{i}" for i in range(n_obs)])
            var = pd.DataFrame(index=[f"GENE_{i}" for i in range(n_vars)])
            
            # Create the AnnData object without feature_types and gene_ids
            adata = ad.AnnData(X=X, obs=obs, var=var)
            adata.write_h5ad(tmp.name)
            
            # Read the file into a BytesIO for the validator
            with open(tmp.name, 'rb') as f:
                file_data = f.read()
            
            # Create a BytesIO object for validation
            stream = BytesIO(file_data)
            
            # Validate the file
            result = validator.validate_stream(stream, is_gzipped=False)
            
            # Check the result
            assert result['valid'] is False
            assert 'errors' in result
            assert 'var.feature_types' in result['errors']
            assert 'var.gene_ids' in result['errors']
            
        finally:
            # Clean up
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

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