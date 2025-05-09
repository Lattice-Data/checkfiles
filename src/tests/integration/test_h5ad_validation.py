"""Integration tests for H5AD file validation."""

import os
import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

try:
    import anndata
    import scanpy as sc
    HAS_ANNDATA = True
except ImportError:
    HAS_ANNDATA = False


@pytest.fixture(scope="session")
def create_h5ad_test_files(h5ad_dir):
    """Create test H5AD files if they don't exist."""
    if not HAS_ANNDATA:
        pytest.skip("anndata and scanpy are required for H5AD tests")
        
    valid_path = h5ad_dir / "valid_h5ad_sample.h5ad"
    invalid_path = h5ad_dir / "invalid_h5ad_sample.h5ad"
    
    # Create valid H5AD file if it doesn't exist
    if not valid_path.exists():
        # Create a simple valid AnnData object
        n_obs = 10  # 10 cells
        n_vars = 15  # 15 genes
        
        # Create random data
        X = np.random.randn(n_obs, n_vars)
        obs = pd.DataFrame(index=[f'cell_{i}' for i in range(n_obs)])
        var = pd.DataFrame(index=[f'gene_{i}' for i in range(n_vars)])
        
        # Add some metadata
        obs['sample'] = ['sample1'] * 5 + ['sample2'] * 5
        var['gene_type'] = np.random.choice(['protein_coding', 'lincRNA'], size=n_vars)
        
        # Create AnnData object
        adata = anndata.AnnData(X=X, obs=obs, var=var)
        
        # Add some standard AnnData attributes
        adata.uns['genome'] = 'hg38'
        adata.uns['feature_counts'] = {'gene': n_vars}
        
        # Save to file
        adata.write(valid_path)
    
    # Create invalid H5AD file if it doesn't exist
    if not invalid_path.exists():
        # Create a simple but invalid H5AD file
        with open(invalid_path, 'wb') as f:
            f.write(b'Not a valid H5AD file')
    
    return h5ad_dir


def test_h5ad_validation(create_h5ad_test_files, temp_log_dir, run_checkfiles):
    """Test validation of valid H5AD files."""
    if not HAS_ANNDATA:
        pytest.skip("anndata and scanpy are required for H5AD tests")
        
    h5ad_dir = create_h5ad_test_files
    valid_h5ad = h5ad_dir / "valid_h5ad_sample.h5ad"
    
    # Skip if the file wasn't created successfully
    if not valid_h5ad.exists():
        pytest.skip(f"Test H5AD file {valid_h5ad} not found")
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run checkfiles on valid H5AD file
    result = run_checkfiles([
        "-l", str(valid_h5ad),
        "-f", "h5ad"
    ], env=env)
    
    # Verify output
    assert result.returncode == 0
    
    # Check progress log
    progress_log = temp_log_dir / "validation_progress.log"
    with open(progress_log, 'r') as f:
        lines = f.readlines()
        assert len(lines) > 1, "Progress log should contain results"


def test_invalid_h5ad(create_h5ad_test_files, temp_log_dir, run_checkfiles):
    """Test validation of invalid H5AD files."""
    if not HAS_ANNDATA:
        pytest.skip("anndata and scanpy are required for H5AD tests")
        
    h5ad_dir = create_h5ad_test_files
    invalid_h5ad = h5ad_dir / "invalid_h5ad_sample.h5ad"
    
    # Skip if the file wasn't created successfully
    if not invalid_h5ad.exists():
        pytest.skip(f"Test invalid H5AD file {invalid_h5ad} not found")
    
    env = os.environ.copy()
    env["CHECKFILES_LOG_DIR"] = str(temp_log_dir)
    
    # Run checkfiles on invalid H5AD file
    result = run_checkfiles([
        "-l", str(invalid_h5ad),
        "-f", "h5ad"
    ], env=env)
    
    # For invalid files, check that validation shows failure
    assert "Files with invalid content: 1" in result.stdout or "Files that failed processing" in result.stdout
    
    # Check progress log
    progress_log = temp_log_dir / "validation_progress.log"
    with open(progress_log, 'r') as f:
        lines = f.readlines()
        if len(lines) > 1:
            result_line = lines[1].strip().split('\t')
            errors = json.loads(result_line[2])
            assert errors, "Should have validation errors" 