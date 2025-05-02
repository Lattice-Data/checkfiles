#!/usr/bin/env python3
"""Create a test H5AD file for manual testing."""

import numpy as np
import pandas as pd
import anndata as ad
import tempfile
import os

def create_test_h5ad():
    """Create a test H5AD file.
    
    Returns:
        Path to the created file
    """
    # Create a simple AnnData object
    n_obs = 10  # 10 cells
    n_vars = 15  # 15 genes
    
    # Create the expression matrix
    X = np.random.normal(size=(n_obs, n_vars))
    
    # Create observation and variable dataframes
    obs = pd.DataFrame(index=[f'CELL_{i}' for i in range(n_obs)])
    var = pd.DataFrame(index=[f'GENE_{i}' for i in range(n_vars)])
    
    # Add feature_types column to var
    var['feature_types'] = ['Gene Expression'] * n_vars
    
    # Add gene_ids column to var with Ensembl IDs
    var['gene_ids'] = [f'ENSG{str(i).zfill(11)}' for i in range(n_vars)]
    var['gene_versions'] = [f'ENSG{str(i).zfill(11)}.1' for i in range(n_vars)]
    
    # Add genome column
    var['genome'] = ['GRCh38'] * n_vars
    
    # Properly add a PAR_Y gene by duplicating it
    # First occurrence
    var.loc[var.index[5], 'gene_ids'] = 'ENSG00000000005_PAR_Y'
    var.loc[var.index[5], 'gene_versions'] = 'ENSG00000000005.1_PAR_Y'
    
    # Second occurrence (duplicate with same ID)
    # We need to add a new row with the same gene symbol but different index position
    # First, extract the current index
    current_index = list(var.index)
    
    # Create a new entry with the same PAR_Y gene ID
    new_row = pd.DataFrame({
        'feature_types': ['Gene Expression'],
        'gene_ids': ['ENSG00000000005_PAR_Y'],
        'gene_versions': ['ENSG00000000005.1_PAR_Y'],
        'genome': ['GRCh38']
    }, index=[current_index[5]])  # Use the same gene symbol as index
    
    # Append the new row
    var = pd.concat([var, new_row])
    
    # Create the AnnData object
    adata = ad.AnnData(X=np.hstack([X, np.zeros((n_obs, 1))]), obs=obs, var=var)
    
    # Save to file
    filename = os.path.join(tempfile.gettempdir(), 'test_data.h5ad')
    adata.write_h5ad(filename)
    
    return filename

if __name__ == '__main__':
    filename = create_test_h5ad()
    print(f'Created test file: {filename}') 