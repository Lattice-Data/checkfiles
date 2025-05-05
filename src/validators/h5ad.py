"""
H5AD/H5 file validator for single-cell data matrices.

This module provides validation for H5AD (.h5ad) and 10x Genomics H5 (.h5) 
files containing single-cell expression data, checking features like:
- Basic HDF5 structure and readability
- Gene ID format compliance
- Feature type validation
- Cell ID validation
- Metadata structure validation
- Compression efficiency

Validation is performed directly on local files. Stream validation is not supported.
"""

import logging
import os
import tempfile
from typing import Dict, Any, Optional, List, Tuple, Set

import numpy as np
# Try to import scanpy but handle if it's not available
try:
    import scanpy as sc
    import pandas as pd
    SCANPY_AVAILABLE = True
except (ImportError, ValueError):
    SCANPY_AVAILABLE = False
    logging.warning("scanpy module not available. H5AD/H5 validation will be limited.")
    
# Try to import h5py but handle if it's not available
try:
    import h5py
    H5PY_AVAILABLE = True
except (ImportError, ValueError):
    H5PY_AVAILABLE = False
    logging.warning("h5py module not available. H5AD/H5 validation will be limited.")

# Assuming BaseValidator is in src.validators.base
from src.validators.base import BaseValidator
    
logger = logging.getLogger(__name__)

class H5adValidator(BaseValidator): # Changed inheritance
    """
    Validator for H5AD (.h5ad) and 10x Genomics H5 (.h5) format files.
    
    This validator ensures that H5AD/H5 files are properly formatted and
    conform to expected standards for single-cell data, including:
    - Basic HDF5 structure validation
    - Validation of gene IDs and feature types
    - Checking cell barcode formats
    - Validating genome annotations
    - Checking for efficient compression
    - Extracting metadata for database consistency
    
    Validation is performed directly on the provided file path.
    """
    
    # Define expected feature types and their mappings to standardized values
    FEATURE_TYPE_MAPPING = {
        'Gene Expression': 'gene',
        'Peaks': 'peak',
        'Antibody Capture': 'antibody capture',
    }
    
    def __init__(self):
        """Initialize the H5AD/H5 validator."""
        super().__init__() # Call BaseValidator's init
        self.has_scanpy = SCANPY_AVAILABLE
        self.has_h5py = H5PY_AVAILABLE
        if not self.has_scanpy:
            logger.warning("scanpy not available, H5AD/H5 validation capabilities will be limited")
        if not self.has_h5py:
            logger.warning("h5py not available, H5AD/H5 validation capabilities will be limited")
    
    # Removed validate_stream method entirely

    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a local H5AD (.h5ad) or 10x H5 (.h5) file.

        Args:
            file_path: Path to the H5AD or H5 file.

        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the file data is valid
            - errors (dict): Any validation errors (format specific)
            - warnings (dict): Any validation warnings (format specific)
            - stats (dict): Data statistics (format specific)
        """
        errors = {}
        warnings = {}
        stats = {}
        adata = None # Initialize AnnData object

        # --- Initial Checks ---
        if not os.path.exists(file_path):
            errors['file_existence'] = f"File not found at path: {file_path}"
            return self.format_validation_result(valid=False, errors=errors)
            
        if not self.has_h5py:
            warnings['h5py_missing'] = "h5py module not available. Cannot perform HDF5 structure checks."
            # Continue validation with scanpy if available, but skip h5py specific checks
        else:
            # Check if it's a valid HDF5 file format
            try:
                is_hdf5 = h5py.is_hdf5(file_path)
                if not is_hdf5:
                    errors['is_hdf5'] = "File is not a valid HDF5 format."
                    return self.format_validation_result(valid=False, errors=errors)
                else:
                    # Add is_hdf5 flag to stats if check passes
                    stats['is_hdf5'] = True
            except Exception as e:
                errors['is_hdf5_check_error'] = f"Error checking HDF5 format: {str(e)}"
                logger.error(f"Error during h5py.is_hdf5 check on {file_path}: {e}", exc_info=True)
                return self.format_validation_result(valid=False, errors=errors)

            # Try opening with h5py to catch basic corruption
            try:
                with h5py.File(file_path, 'r') as f:
                    # Basic check passed
                    logger.debug(f"Successfully opened {file_path} with h5py.")
            except Exception as e:
                errors['h5py_open_error'] = f"Failed to open file with h5py: {str(e)}"
                logger.error(f"Error opening {file_path} with h5py: {e}", exc_info=True)
                return self.format_validation_result(valid=False, errors=errors)

        if not self.has_scanpy:
            warnings['scanpy_missing'] = "scanpy module not available. Cannot perform AnnData content validation."
            # If h5py checks passed, consider valid but incomplete
            return self.format_validation_result(valid=len(errors) == 0, errors=errors, warnings=warnings)

        # --- Load AnnData Object ---
        try:
            logger.info(f"Attempting to read file with scanpy: {file_path}")
            if file_path.lower().endswith('.h5'):
                logger.debug("Reading as 10x H5 format.")
                # Note: gex_only=False loads all feature types if present
                adata = sc.read_10x_h5(file_path, gex_only=False) 
            elif file_path.lower().endswith('.h5ad'):
                logger.debug("Reading as H5AD format.")
                adata = sc.read_h5ad(file_path, backed='r')
            else:
                # Should not happen if initial HDF5 checks passed, but handle defensively
                errors['file_extension'] = "File extension is neither .h5 nor .h5ad."
                return self.format_validation_result(valid=False, errors=errors)
                
            logger.info(f"Successfully read file with scanpy: {file_path}")

        except FileNotFoundError:
             errors['file_not_found'] = f"Scanpy could not find file: {file_path}"
             return self.format_validation_result(valid=False, errors=errors)
        except Exception as e:
            errors['scanpy_read_error'] = f"Error reading file with scanpy: {str(e)}"
            logger.error(f"Error reading file {file_path} with scanpy: {e}", exc_info=True)
            return self.format_validation_result(valid=False, errors=errors, warnings=warnings, stats=stats)

        # --- AnnData Content Validation ---
        if adata:
            try:
                content_results = self._validate_anndata_content(adata)
                errors.update(content_results.get('errors', {}))
                warnings.update(content_results.get('warnings', {}))
                stats.update(content_results.get('stats', {}))
            except Exception as e:
                errors['anndata_validation_error'] = f"Unexpected error during AnnData content validation: {str(e)}"
                logger.error(f"Error during AnnData content validation for {file_path}: {e}", exc_info=True)

        # --- Compression Check ---
        if adata: # Only check compression if adata loaded successfully
             try:
                 self._check_compression(file_path, adata, errors)
             except Exception as e:
                 errors['compression_check_error'] = f"Error during compression check: {str(e)}"
                 logger.error(f"Error during compression check for {file_path}: {e}", exc_info=True)

        # Determine overall validity
        valid = len(errors) == 0
        
        # Critical check - override validation status if we have 'validated' explicitly set in stats
        if 'validated' in stats and stats['validated'] is False:
            valid = False
            logger.warning(f"Forcing validation to fail due to critical errors in {file_path}")
        
        return self.format_validation_result(
            valid=valid,
            errors=errors,
            warnings=warnings,
            stats=stats
        )

    def _validate_anndata_content(self, adata) -> Dict[str, Any]:
        """
        Validate the content of an AnnData object.
        
        Args:
            adata: AnnData object loaded by scanpy
            
        Returns:
            Dictionary with validation results for AnnData content
        """
        errors = {}
        warnings = {}
        stats = {}
        
        try:
            # Extract basic statistics
            stats['observation_count'] = adata.obs.shape[0]
            stats['variable_count'] = adata.var.shape[0] # Added variable count
            
            # Validate feature types
            self._validate_feature_types(adata, errors, stats)
            
            # Validate gene IDs
            self._validate_gene_ids(adata, errors, warnings, stats) # Pass stats
            
            # Validate genomes
            self._validate_genomes(adata, stats)
            
            # Validate cell IDs
            self._validate_cell_ids(adata, errors)
            
            # Check for date-formatted symbols
            self._check_date_formatted_symbols(adata, errors)
            
        except Exception as e:
            # Catch unexpected errors during specific validation steps
            errors['anndata_content_error'] = f"Internal error during content validation: {str(e)}"
            logger.error(f"Internal error during AnnData content validation: {e}", exc_info=True)
            
        return {
            'errors': errors,
            'warnings': warnings,
            'stats': stats
        }

    def _check_compression(self, original_path: str, adata, errors: Dict[str, str]) -> None:
        """
        Check if the AnnData object could be significantly smaller with gzip compression.

        Args:
            original_path: Path to the original file.
            adata: The loaded AnnData object.
            errors: Dictionary to add errors to.
        """
        temp_gzipped_path = None
        try:
            original_size = os.path.getsize(original_path)
            
            # Use a secure temporary file
            fd, temp_gzipped_path = tempfile.mkstemp(suffix=".h5ad")
            os.close(fd) # Close descriptor, adata.write uses the path

            logger.debug(f"Writing temporary compressed file to {temp_gzipped_path}")
            adata.write(filename=temp_gzipped_path, compression='gzip')
            compressed_size = os.path.getsize(temp_gzipped_path)
            logger.debug(f"Original size: {original_size}, Compressed size: {compressed_size}")

            # Check if original is > 1.5x larger than compressed
            if original_size > (compressed_size * 1.5):
                errors['compression'] = (
                    f'File size ({original_size} bytes) is >1.5x larger than '
                    f'potential gzip compressed size ({compressed_size} bytes). '
                    'Consider re-saving with compression.'
                )
        except Exception as e:
            # Log error but don't necessarily invalidate the file for this
            logger.warning(f"Could not perform compression check on {original_path}: {e}", exc_info=True)
            errors['compression_check_failed'] = f"Failed to perform compression check: {str(e)}"
        finally:
            # Clean up the temporary file
            if temp_gzipped_path and os.path.exists(temp_gzipped_path):
                try:
                    os.unlink(temp_gzipped_path)
                    logger.debug(f"Deleted temporary compressed file {temp_gzipped_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary compressed file {temp_gzipped_path}: {e}")


    # --- Existing validation helpers (modified slightly for consistency) ---
    
    def _validate_feature_types(self, adata, errors: Dict[str, str], stats: Dict[str, Any]) -> None:
        """
        Validate feature types in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
            stats: Dictionary to add statistics to
        """
        # CRITICAL CHECK - ALWAYS ENFORCE
        # This is a required field for all h5ad files
        if 'feature_types' not in adata.var.columns:
            errors['var.feature_types'] = 'is missing'
            logger.warning("Required field 'feature_types' is missing in var columns")
            # Still add stats for file size, observation count etc.
            stats['validated'] = False
            return
            
        feature_counts = []
        # Use value_counts(dropna=False) to include potential NaN types
        for k, v in adata.var['feature_types'].value_counts(dropna=False).to_dict().items():
            # Handle potential None/NaN keys
            feature_name = str(k) if pd.notna(k) else "Undefined" 
            key = self.FEATURE_TYPE_MAPPING.get(feature_name, feature_name)
            feature_counts.append({'feature_type': key, 'feature_count': v})
            if pd.isna(k):
                 errors['var.feature_types[Undefined]'] = 'Feature type is missing/NaN'
            elif feature_name not in self.FEATURE_TYPE_MAPPING:
                errors[f'var.feature_types[{feature_name}]'] = 'not a valid feature type'
                
        stats['feature_counts'] = feature_counts
    
    def _validate_gene_ids(self, adata, errors: Dict[str, str], warnings: Dict[str, str], stats: Dict[str, Any]) -> None: # Added stats
        """
        Validate gene IDs in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
            warnings: Dictionary to add warnings to
            stats: Dictionary to add statistics to
        """
        # CRITICAL CHECK - ALWAYS ENFORCE
        # This is a required field for all h5ad files
        if 'gene_ids' not in adata.var.columns:
            errors['var.gene_ids'] = 'is missing'
            logger.warning("Required field 'gene_ids' is missing in var columns")
            # Ensure validation status is captured
            stats['validated'] = False
            # Check if index itself might contain gene IDs
            if all(g.startswith('ENS') for g in adata.var.index):
                 warnings['var.gene_ids_missing_but_index_ok'] = 'var.gene_ids is missing, but var.index contains ENS IDs.'
                 stats['feature_keys'] = ['Ensembl gene ID'] # Assume index is feature key
            return
            
        # Ensure gene_ids is treated as string type for checks
        gene_ids_series = adata.var['gene_ids'].astype(str)

        if 'feature_types' in adata.var.columns:
            feature_types_series = adata.var['feature_types'].astype(str)
            # Check if gene expressions have ENSG format
            # Handle potential NaN in feature_types or gene_ids
            gene_expr_mask = (feature_types_series == 'Gene Expression') & gene_ids_series.notna()
            not_ensg = [g for g in gene_ids_series[gene_expr_mask] if not g.startswith('ENS')]
            if len(not_ensg) > 0:
                # Report only a sample if too many
                sample_size = min(len(not_ensg), 5)
                errors['var.gene_ids_not_ensg'] = (
                    f"{len(not_ensg)} Gene Expression features in var.gene_ids "
                    f"not ENS-formatted (e.g., {not_ensg[:sample_size]})"
                )
                
            # Check gene versions outside of Peaks and Antibody Capture
            non_special_mask = (
                ~feature_types_series.isin(['Peaks', 'Antibody Capture']) &
                gene_ids_series.notna()
            )
            with_version = [g for g in gene_ids_series[non_special_mask] if '.' in g]
        else:
            # If no feature_types column, just check all gene_ids for versions
            warnings['missing_feature_types_for_gene_id_check'] = "Cannot definitively check gene ID versions without 'feature_types' column."
            with_version = [g for g in gene_ids_series[gene_ids_series.notna()] if '.' in g]
            
        if len(with_version) > 0:
            # Report only a sample if too many
            sample_size = min(len(with_version), 5)
            errors['var.gene_ids_version_present'] = (
                f"{len(with_version)} non-peak/antibody gene IDs contain versions "
                f"('.') which should be removed (e.g., {with_version[:sample_size]})"
            )
            
        # Validate PAR_Y genes
        self._validate_par_y_genes(adata, errors) # Pass adata directly
            
        # Check gene versions column if it exists
        if 'gene_versions' in adata.var.columns:
            gene_versions_series = adata.var['gene_versions'].astype(str)
            # Ensure versions are in ENSGxxxx.N format (contains '.')
            # Handle potential NaN
            version_mask = gene_versions_series.notna()
            without_version_dot = [g for g in gene_versions_series[version_mask] if '.' not in g]
            if len(without_version_dot) > 0:
                sample_size = min(len(without_version_dot), 5)
                errors['var.gene_versions_format'] = (
                    f"{len(without_version_dot)} IDs in var.gene_versions lack version suffix "
                    f"('.' format) (e.g., {without_version_dot[:sample_size]})"
                )
                
        # Check if all feature keys (index) are Ensembl gene IDs if not already set
        if 'feature_keys' not in stats and all(isinstance(g, str) and g.startswith('ENS') for g in adata.var.index):
            stats['feature_keys'] = ['Ensembl gene ID']

    def _validate_par_y_genes(self, adata, errors: Dict[str, str]) -> None:
        """
        Validate PAR_Y genes in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
        """
        try:
            gene_ids_series = adata.var['gene_ids'].astype(str)
            has_gene_versions = 'gene_versions' in adata.var.columns
            if has_gene_versions:
                 gene_versions_series = adata.var['gene_versions'].astype(str)

            found_par_y_error = False # Flag to see if we find any PAR_Y

            # Iterate through all gene IDs
            for idx, g_id in gene_ids_series.items():
                 # --- Add detailed logging here ---
                 logger.debug(f"Checking g_id: {repr(g_id)} (Type: {type(g_id)})") 
                 # --- End logging ---
                 # Use case-insensitive check for finding candidates
                 if 'PAR_Y' in g_id.upper(): 
                    found_par_y_error = True # Mark that we found one
                    logger.debug(f"Checking potential PAR_Y gene ID: {g_id}")
                    
                    # --- Check Suffix ---
                    if not g_id.endswith('_PAR_Y'):
                         errors[f'PAR_Y_id_suffix[{g_id}]'] = f"Expecting PAR_Y gene ID '{g_id}' to end with '_PAR_Y'"
                         logger.warning(f"PAR_Y suffix error for {g_id}")
                         # Don't check other things if suffix is wrong
                         continue 
                         
                    # --- Check Duplication (only for correctly suffixed) ---
                    matching_symbols = adata.var.index[gene_ids_series == g_id]
                    if len(matching_symbols) < 2:
                         errors[f'PAR_Y_duplication[{g_id}]'] = f'Expecting gene ID {g_id} to correspond to at least 2 symbols (found {len(matching_symbols)})'
                         logger.warning(f"PAR_Y duplication error for {g_id}")
                         
                    # --- Check Version Consistency (only for correctly suffixed) ---
                    if has_gene_versions:
                        # Get version corresponding to this specific index `idx`
                        ver = gene_versions_series.loc[idx]
                        if pd.notna(ver) and '.' in ver:
                            base_id_from_version = '_'.join([ver.split('.')[0]] + ver.split('_')[1:])
                            if g_id != base_id_from_version:
                                errors[f'PAR_Y_version_mismatch[{g_id}]'] = f"PAR_Y gene ID '{g_id}' does not match derived ID from version '{ver}' ('{base_id_from_version}')"
                        elif pd.notna(ver):
                            errors[f'PAR_Y_version_format[{g_id}]'] = f"PAR_Y gene version '{ver}' for ID '{g_id}' lacks '.' format"

            if not found_par_y_error:
                 logger.debug("No gene IDs containing 'PAR_Y' were found during iteration.")

        except Exception as e:
            errors['par_y_check_error'] = f"Error during PAR_Y gene validation: {str(e)}"
            logger.warning(f"Error validating PAR_Y genes: {e}", exc_info=True)

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
        Validate cell IDs (observation index) in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
        """
        try:
            # Check for suffixes like '.1', '.2' etc.
            # Convert index to string just in case it's not already
            obs_index_str = adata.obs.index.astype(str)
            # Regex to find indices ending in '.' followed by one or more digits
            incorrect_cell_ids_mask = obs_index_str.str.contains(r'\.\d+$', regex=True, na=False)
            incorrect_cell_ids = adata.obs.index[incorrect_cell_ids_mask].tolist()
            
            if len(incorrect_cell_ids) > 0:
                 sample_size = min(len(incorrect_cell_ids), 5)
                 errors['cell_id_suffix'] = (
                     f"{len(incorrect_cell_ids)} obs.index values end with '.<digits>' "
                     f"(e.g., {incorrect_cell_ids[:sample_size]}), which may indicate incorrect formatting."
                 )
        except Exception as e:
             errors['cell_id_check_error'] = f"Error validating cell IDs: {str(e)}"
             logger.warning(f"Error validating cell IDs: {e}", exc_info=True)

    def _check_date_formatted_symbols(self, adata, errors: Dict[str, str]) -> None:
        """
        Check for date-formatted symbols in the AnnData object.
        
        Args:
            adata: AnnData object
            errors: Dictionary to add errors to
        """
        try:
            # Ensure var index is string type
            var_index_str = adata.var.index.astype(str)
            check_dates = ['Mar-1', '1-Mar', 'Dec-1', '1-Dec'] # Add other problematic patterns if known
            # Use isin for efficient checking
            date_symbols_mask = var_index_str.isin(check_dates)
            date_symbols = adata.var.index[date_symbols_mask].tolist()
            
            if len(date_symbols) > 0:
                errors['date_formatted_symbols'] = f"Symbols present that might be auto-reformatted dates: {','.join(date_symbols)}" 
        except Exception as e:
             errors['date_symbol_check_error'] = f"Error checking for date-formatted symbols: {str(e)}"
             logger.warning(f"Error checking date symbols: {e}", exc_info=True) 

    def validate_s3_file(self, s3_uri: str, debug: bool = False) -> Dict[str, Any]:
        """
        Validate an S3-stored H5AD file.
        
        Args:
            s3_uri: S3 URI of the file to validate
            debug: Whether to enable debug output
            
        Returns:
            Dictionary with validation results
        """
        import os
        import tempfile
        import subprocess
        import uuid
        
        logger.info(f"H5AD validation of S3 file: {s3_uri}")
        
        # Create a temporary filename with a recognizable pattern
        filename = os.path.basename(s3_uri)
        prefix = "h5ad_" + str(hash(s3_uri) % 100000000) + "_"
        temp_dir = "/mnt/scratch" if os.path.exists("/mnt/scratch") else tempfile.gettempdir()
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, prefix + filename)
        
        try:
            # Use AWS CLI to download the file
            logger.info(f"Downloading file: aws s3 cp {s3_uri} {temp_file}")
            cmd = f"aws s3 cp {s3_uri} {temp_file}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Failed to download file: {result.stderr}"
                logger.error(error_msg)
                return self.format_validation_result(
                    valid=False,
                    errors={"download_error": error_msg}
                )
            
            if debug:
                logger.debug(f"AWS CLI output: {result.stdout}")
            
            # Validate the downloaded file
            logger.info(f"Validating downloaded file: {temp_file}")
            validation_result = self.validate_file(temp_file)
            
            # Ensure errors are surfaced properly
            if not validation_result.get('valid', False) and validation_result.get('errors'):
                logger.warning(f"Validation failed for {s3_uri}: {validation_result['errors']}")
            
            logger.info(f"Validation complete for {s3_uri}")
            
            # Return the result
            return validation_result
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error validating S3 file {s3_uri}: {str(e)}")
            logger.error(f"Traceback: {error_traceback}")
            
            return self.format_validation_result(
                valid=False, 
                errors={"validation_error": f"Error validating file: {str(e)}"}
            )
        finally:
            # Clean up the temporary file
            try:
                if os.path.exists(temp_file):
                    logger.info(f"Cleaning up temporary file: {temp_file}")
                    os.remove(temp_file)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {temp_file}: {str(e)}") 