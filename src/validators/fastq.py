"""
FASTQ file and stream validator with Rust acceleration.
"""
import os
import logging
from typing import Dict, Any, BinaryIO, Optional, Tuple, Union

from src.validators.base import BaseValidator, ValidationError
from src.wrappers.seqkit import SeqKitWrapper, SeqKitError

# Import the Rust module (will be built by setuptools-rust)
try:
    import fastq_validator
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.warning("Rust FASTQ validator not available, falling back to Python implementation")

logger = logging.getLogger(__name__)


class FastqValidator(BaseValidator):
    """Validator for FASTQ format files and streams.
    
    This validator can use:
    1. Rust-based validation (preferred, if available) for maximum performance
    2. SeqKit-based validation as a fallback
    
    It supports both file-based and streaming validation.
    """
    
    def __init__(self):
        """Initialize the FASTQ validator."""
        super().__init__()
        self.seqkit = SeqKitWrapper()
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """Validate a FASTQ file.
        
        Args:
            file_path: Path to the FASTQ file to validate
            
        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the file is valid
            - errors (dict): Any validation errors
            - warnings (dict): Any validation warnings
            - stats (dict): File statistics
        """
        if not os.path.exists(file_path):
            return self.format_validation_result(
                valid=False,
                errors={"file_not_found": f"File not found: {file_path}"}
            )
        
        errors = {}
        warnings = {}
        stats = {}
        
        # Try to use Rust implementation if available
        if RUST_AVAILABLE:
            try:
                # Fast validation with Rust
                is_valid = fastq_validator.validate_fastq(file_path)
                if not is_valid:
                    return self.format_validation_result(
                        valid=False,
                        errors={"invalid_format": "Invalid FASTQ format: header/sequence/quality structure issues"}
                    )
                
                # Get basic stats from Rust
                rust_stats = fastq_validator.fastq_stats(file_path)
                stats.update(rust_stats)
                
                logger.debug(f"Validated FASTQ file with Rust: {file_path}")
                
            except ValueError as e:
                # If Rust validation fails with an error, log it and continue with fallback
                warnings["rust_validation_warning"] = f"Rust validation error: {str(e)}"
                logger.warning(f"Rust validation failed, falling back to SeqKit: {str(e)}")
        
        # If Rust is not available or validation failed, use SeqKit
        if not RUST_AVAILABLE or "rust_validation_warning" in warnings:
            try:
                # Perform SeqKit validation
                seqkit_errors = self._validate_with_seqkit(file_path)
                if seqkit_errors:
                    errors.update(seqkit_errors)
                    return self.format_validation_result(valid=False, errors=errors)
                
                # Get stats from SeqKit if Rust didn't provide them
                if not stats:
                    seqkit_stats = self.seqkit.stats(file_path=file_path)
                    stats.update(seqkit_stats)
                    
                logger.debug(f"Validated FASTQ file with SeqKit: {file_path}")
                    
            except Exception as e:
                errors["validation_error"] = f"Error during validation: {str(e)}"
                logger.error(f"SeqKit validation failed: {str(e)}")
                return self.format_validation_result(valid=False, errors=errors)
        
        # Additional validations and quality checks based on stats
        validation_result = self._perform_additional_validations(stats)
        errors.update(validation_result.get("errors", {}))
        warnings.update(validation_result.get("warnings", {}))
        
        # Determine if valid (no errors, even if there are warnings)
        valid = len(errors) == 0
        
        return self.format_validation_result(
            valid=valid,
            errors=errors,
            warnings=warnings,
            stats=stats
        )
    
    def validate_stream(self, input_stream: BinaryIO) -> Dict[str, Any]:
        """Validate a FASTQ data stream.
        
        Args:
            input_stream: Binary stream containing FASTQ data
            
        Returns:
            Dictionary with validation results including:
            - valid (bool): Whether the stream data is valid
            - errors (dict): Any validation errors
            - warnings (dict): Any validation warnings
            - stats (dict): Data statistics
        """
        errors = {}
        warnings = {}
        stats = {}
        
        # Attempt to use Rust for streaming validation if available
        if RUST_AVAILABLE:
            try:
                # Read the stream into memory for Rust processing
                # Note: For very large streams, we might need a more memory-efficient approach
                data = input_stream.read()
                
                # Validate format with Rust
                is_valid = fastq_validator.validate_fastq_from_bytes(data)
                if not is_valid:
                    return self.format_validation_result(
                        valid=False,
                        errors={"invalid_format": "Invalid FASTQ format in stream: header/sequence/quality issues"}
                    )
                
                # Get statistics
                rust_stats = fastq_validator.fastq_stats_from_bytes(data)
                stats.update(rust_stats)
                
                # Reset stream position if possible
                try:
                    input_stream.seek(0)
                except (AttributeError, IOError):
                    warnings["stream_warning"] = "Unable to reset stream position after validation"
                    
                logger.debug("Validated FASTQ stream with Rust")
                
            except ValueError as e:
                # If Rust validation fails with an error, log it and continue with fallback
                warnings["rust_validation_warning"] = f"Rust stream validation error: {str(e)}"
                logger.warning(f"Rust stream validation failed, falling back to SeqKit: {str(e)}")
                
                # Try to reset stream position if possible
                try:
                    input_stream.seek(0)
                except (AttributeError, IOError):
                    errors["stream_error"] = "Unable to reset stream position after failed validation"
                    return self.format_validation_result(valid=False, errors=errors)
        
        # If Rust is not available or validation failed, use SeqKit
        if not RUST_AVAILABLE or "rust_validation_warning" in warnings:
            try:
                # Validate with SeqKit
                seqkit_result = self.seqkit.validate_fastq_streaming(input_stream)
                
                if not seqkit_result.get("valid", False):
                    errors["invalid_format"] = seqkit_result.get("error", "Invalid FASTQ format in stream")
                    return self.format_validation_result(valid=False, errors=errors)
                
                # Get stats if not already provided by Rust
                if not stats:
                    stats.update(seqkit_result.get("stats", {}))
                    
                logger.debug("Validated FASTQ stream with SeqKit")
                
            except SeqKitError as e:
                errors["seqkit_error"] = f"SeqKit stream validation failed: {str(e)}"
                logger.error(f"SeqKit stream validation failed: {str(e)}")
                return self.format_validation_result(valid=False, errors=errors)
            except Exception as e:
                errors["validation_error"] = f"Unexpected error during stream validation: {str(e)}"
                logger.error(f"Unexpected error during stream validation: {str(e)}")
                return self.format_validation_result(valid=False, errors=errors)
        
        # Additional validations and quality checks based on stats
        validation_result = self._perform_additional_validations(stats)
        errors.update(validation_result.get("errors", {}))
        warnings.update(validation_result.get("warnings", {}))
        
        # Determine if valid (no errors, even if there are warnings)
        valid = len(errors) == 0
        
        return self.format_validation_result(
            valid=valid,
            errors=errors,
            warnings=warnings,
            stats=stats
        )
    
    def _validate_with_seqkit(self, file_path: str) -> Dict[str, str]:
        """Validate FASTQ using SeqKit.
        
        Args:
            file_path: Path to the FASTQ file to validate
            
        Returns:
            Dictionary of errors (empty if validation passed)
        """
        errors = {}
        try:
            # Basic format check - try to read first few records
            self.seqkit.head(file_path=file_path, num_records=5)
        except SeqKitError as e:
            errors["invalid_format"] = f"Invalid FASTQ format: {str(e)}"
        except Exception as e:
            errors["validation_error"] = f"Error during SeqKit validation: {str(e)}"
        return errors
    
    def _perform_additional_validations(self, stats: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Perform additional validations on FASTQ statistics.
        
        Args:
            stats: Dictionary of FASTQ statistics
            
        Returns:
            Dictionary with errors and warnings
        """
        errors = {}
        warnings = {}
        
        # Check if file is empty
        read_count = stats.get("read_count", 0)
        if read_count == 0:
            errors["empty_file"] = "FASTQ data contains no sequences"
            return {"errors": errors, "warnings": warnings}
        
        # Check for unusually short reads
        min_len = stats.get("min_length", 0)
        if min_len < 10:
            warnings["short_reads"] = f"Data contains very short reads (minimum length: {min_len})"
        
        # Check read length variability
        min_len = stats.get("min_length", 0)
        max_len = stats.get("max_length", 0)
        avg_len = stats.get("avg_length", 0)
        
        # If min and max lengths are very different, reads are variable length
        if max_len > 0 and min_len > 0 and (max_len - min_len) > 0.5 * avg_len:
            warnings["variable_length"] = f"Read lengths are highly variable (min: {min_len}, max: {max_len})"
        
        # Check for unusually small total sequence volume
        total_length = stats.get("total_length", 0)
        if total_length < 1000 and read_count > 0:
            warnings["low_sequence_volume"] = f"Total sequence volume is very small: {total_length} bp"
        
        return {"errors": errors, "warnings": warnings}