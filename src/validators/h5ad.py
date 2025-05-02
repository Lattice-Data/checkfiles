"""
H5AD file validator for single-cell data matrices.

This module provides validation for H5AD files (AnnData objects) 
containing single-cell expression data, checking features like:
- Gene ID format compliance
- Feature type validation
- Cell ID validation
- Metadata structure validation

Note: This validator is used for both files with 'h5ad' format and files with 'hdf5' format
that have the .h5ad extension.
"""

import logging
import os
from typing import Dict, Any, BinaryIO, Optional, List, Tuple, Set

import numpy as np

from src.validators.hdf5 import Hdf5Validator

# Try to import scanpy but handle if it's not available
try:
    import scanpy as sc
    import pandas as pd
    SCANPY_AVAILABLE = True
except (ImportError, ValueError):
    SCANPY_AVAILABLE = False
    logging.warning("scanpy module not available. H5AD validation will be limited.")
    
# Try to import h5py but handle if it's not available
try:
    import h5py
    H5PY_AVAILABLE = True
except (ImportError, ValueError):
    H5PY_AVAILABLE = False
    logging.warning("h5py module not available. H5AD validation will be limited.")
    
logger = logging.getLogger(__name__)

class H5adValidator(Hdf5Validator):
    """
    Validator for H5AD format files (AnnData objects).
    
    This validator ensures that H5AD files are properly formatted and
    conform to expected standards for single-cell data, including:
    - Validation of gene IDs and feature types
    - Checking cell barcode formats
    - Validating genome annotations
    - Extracting metadata for database consistency
    
    Note: This validator is used for both files with explicit 'h5ad' format
    and files with 'hdf5' format that have the .h5ad extension.
    """
    
    # Define expected feature types and their mappings to standardized values
    FEATURE_TYPE_MAPPING = {
        'Gene Expression': 'gene',
        'Peaks': 'peak',
        'Antibody Capture': 'antibody capture',
    }
    
    def __init__(self):
        """Initialize the H5AD validator."""
        super().__init__()
        self.has_scanpy = SCANPY_AVAILABLE
        if not self.has_scanpy:
            logger.warning("scanpy not available, H5AD validation capabilities will be limited")
    
    def validate_stream(self, input_stream: BinaryIO, is_gzipped: bool = False) -> Dict[str, Any]:
        """
        Validate an H5AD data stream.
        
        Args:
            input_stream: Binary stream containing H5AD data
            is_gzipped: Whether the stream contains gzipped data
            
        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the stream data is valid
            - errors (dict): Any validation errors (format specific)
            - warnings (dict): Any validation warnings (format specific)
            - stats (dict): Data statistics (format specific, like observation counts)
        """
        # First perform basic HDF5 validation
        base_result = super().validate_stream(input_stream, is_gzipped)
        
        # If there were errors in the basic HDF5 validation, return those
        if not base_result.get('valid', False):
            return base_result
            
        errors = base_result.get('errors', {})
        warnings = base_result.get('warnings', {})
        stats = base_result.get('stats', {})
        
        # If scanpy is not available, we can't do specialized validation
        if not self.has_scanpy:
            warnings['scanpy_missing'] = "scanpy module not available for full H5AD validation"
            return self.format_validation_result(
                valid=True,  # Still consider valid as we can't check
                warnings=warnings,
                stats=stats
            )
            
        # Create a temporary file from the stream for scanpy to read if not seekable
        temp_path = None
        try:
            # Check if the stream is seekable
            is_seekable = self.is_stream_seekable(input_stream)
            
            if not is_seekable:
                # Use our parent class method to create a temp file
                temp_path, temp_file = self.create_temp_file_from_stream(input_stream, is_gzipped)
                validation_result = self._validate_h5ad_file(temp_path)
                # Close the temp file here - it will be deleted in finally block
                temp_file.close()
            else:
                # For seekable streams, we can use stream position management
                original_pos = input_stream.tell()
                input_stream.seek(0)  # Reset stream position
                
                # Use a temporary file just for AnnData since it expects a file path
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name
                    # Write the stream to the temporary file
                    buffer_size = 1024 * 1024  # 1MB buffer
                    import shutil
                    shutil.copyfileobj(input_stream, temp_file, buffer_size)
                
                # Now validate the temporary file
                validation_result = self._validate_h5ad_file(temp_path)
                
                # Restore original stream position
                input_stream.seek(original_pos)
                
            # Merge results with base validation
            errors.update(validation_result.get('errors', {}))
            warnings.update(validation_result.get('warnings', {}))
            stats.update(validation_result.get('stats', {}))
                
        except Exception as e:
            errors['h5ad_validation_error'] = f"Error during H5AD validation: {str(e)}"
            logger.error(f"Error during H5AD validation: {e}", exc_info=True)
        finally:
            # Clean up the temporary file
            if temp_path:
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Deleted temporary H5AD file {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_path}: {e}")
                
        # Determine if valid (no errors, even if there are warnings)
        valid = len(errors) == 0
        
        return self.format_validation_result(
            valid=valid,
            errors=errors,
            warnings=warnings,
            stats=stats
        )
    
    def _validate_h5ad_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate an H5AD file using scanpy.
        
        Args:
            file_path: Path to the H5AD file
            
        Returns:
            Dictionary with validation results
        """
        errors = {}
        warnings = {}
        stats = {}
        
        try:
            # Read the file with scanpy
            adata = sc.read_h5ad(file_path, backed='r')
            
            # Extract basic statistics
            stats['observation_count'] = adata.obs.shape[0]
            
            # Validate feature types
            self._validate_feature_types(adata, errors, stats)
            
            # Validate gene IDs
            self._validate_gene_ids(adata, errors, warnings)
            
            # Validate genomes
            self._validate_genomes(adata, stats)
            
            # Validate cell IDs
            self._validate_cell_ids(adata, errors)
            
            # Check for date-formatted symbols
            self._check_date_formatted_symbols(adata, errors)
            
        except Exception as e:
            errors['file_reading_error'] = f"Error reading H5AD file: {str(e)}"
            logger.error(f"Error reading H5AD file {file_path}: {e}", exc_info=True)
            
        return {
            'errors': errors,
            'warnings': warnings,
            'stats': stats
        }
    
    def _validate_feature_types(self, adata, errors: Dict[str, str], stats: Dict[str, Any]) -> None:
        """
        Validate feature types in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
            stats: Dictionary to add statistics to
        """
        if 'feature_types' not in adata.var.columns:
            errors['var.feature_types'] = 'is missing'
            return
            
        feature_counts = []
        for k, v in adata.var['feature_types'].value_counts().to_dict().items():
            key = self.FEATURE_TYPE_MAPPING.get(k, k)
            feature_counts.append({'feature_type': key, 'feature_count': v})
            if k not in self.FEATURE_TYPE_MAPPING:
                errors[f'var.feature_types[{k}]'] = 'not a valid feature type'
                
        stats['feature_counts'] = feature_counts
    
    def _validate_gene_ids(self, adata, errors: Dict[str, str], warnings: Dict[str, str]) -> None:
        """
        Validate gene IDs in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
            warnings: Dictionary to add warnings to
        """
        if 'gene_ids' not in adata.var.columns:
            errors['var.gene_ids'] = 'is missing'
            return
            
        if 'feature_types' in adata.var.columns:
            # Check if gene expressions have ENSG format
            not_ensg = [g for g in adata.var[adata.var['feature_types'] == 'Gene Expression']['gene_ids'] 
                         if not g.startswith('ENS')]
            if len(not_ensg) > 0:
                errors['var.gene_ids'] = f"{len(not_ensg)} features in var.gene_ids not ENS-formatted"
                
            # Check gene versions outside of Peaks and Antibody Capture
            with_version = [g for g in adata.var[~adata.var['feature_types'].isin(['Peaks', 'Antibody Capture'])]['gene_ids']
                              if '.' in g]
        else:
            # If no feature_types column, just check all gene_ids
            with_version = [g for g in adata.var['gene_ids'] if '.' in g]
            
        if len(with_version) > 0:
            errors['ENSG format'] = f"{len(with_version)} versions in var.gene_ids"
            
        # Validate PAR_Y genes
        self._validate_par_y_genes(adata, errors)
            
        # Check gene versions
        if 'gene_versions' in adata.var.columns:
            without_version = [g for g in adata.var['gene_versions'] if '.' not in g]
            if len(without_version) > 0:
                errors['ENSG.N format'] = f"{len(without_version)} IDs without version in var.gene_versions"
                
        # Check if all feature keys are Ensembl gene IDs
        if len([g for g in adata.var.index if g.startswith('ENS')]) == adata.var.shape[0]:
            stats = {}  # Create stats if not passed
            stats['feature_keys'] = ['Ensembl gene ID']
    
    def _validate_par_y_genes(self, adata, errors: Dict[str, str]) -> None:
        """
        Validate PAR_Y genes in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
        """
        pary_genes = [g for g in adata.var['gene_ids'] if 'PAR_Y' in g]
        for g in pary_genes:
            symb = adata.var.loc[adata.var['gene_ids'] == g].index[0]
            if adata.var[adata.var.index == symb].shape[0] < 2:
                errors['PAR_Y symbols'] = 'expecting PAR_Y symbols to be duplicated'
            if not g.endswith('PAR_Y'):
                errors['PAR_Y ID'] = 'expecting PAR_Y genes to end with PAR_Y'
            if 'gene_versions' in adata.var.columns:
                ver = adata.var.loc[adata.var['gene_ids'] == g]['gene_versions'][0]
                if g != '_'.join([ver.split('.')[0]] + ver.split('_')[1:]):
                    errors['PAR_Y version'] = 'PAR_Y gene version does not match ID'
    
    def _validate_genomes(self, adata, stats: Dict[str, Any]) -> None:
        """
        Validate genome information in the AnnData object.
        
        Args:
            adata: AnnData object
            stats: Dictionary to add statistics to
        """
        if 'genome' in adata.var.columns:
            stats['genomes'] = adata.var['genome'].unique().tolist()
    
    def _validate_cell_ids(self, adata, errors: Dict[str, str]) -> None:
        """
        Validate cell IDs in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
        """
        incorrect_cell_ids = [c for c in adata.obs.index if c.endswith('.1')]
        if len(incorrect_cell_ids) > 0:
            errors['cell_id suffix'] = 'obs.index values should not end in .1'
    
    def _check_date_formatted_symbols(self, adata, errors: Dict[str, str]) -> None:
        """
        Check for date-formatted symbols in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
        """
        check_dates = ['Mar-1', '1-Mar', 'Dec-1', '1-Dec']
        date_symbols = [s for s in check_dates if s in adata.var.index]
        if len(date_symbols) > 0:
            errors['date-formatted symbols'] = f"symbols present that have been reformatted: {','.join(date_symbols)}" 