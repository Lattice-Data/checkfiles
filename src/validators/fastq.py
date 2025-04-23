"""
FASTQ file and stream validator with Rust implementation.
"""
import os
import logging
from typing import Dict, Any, BinaryIO

from src.validators.base import BaseValidator

# Import the Rust module (will be built by setuptools-rust)
try:
    import fastq_validator
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.error("Rust FASTQ validator not available. This tool requires Rust implementation.")
    raise ImportError("Rust FASTQ validator is required but not available")

logger = logging.getLogger(__name__)


class FastqValidator(BaseValidator):
    """Validator for FASTQ format files and streams.
    
    This validator uses Rust-based validation for maximum performance.
    It supports both file-based and streaming validation.
    """
    
    def __init__(self):
        """Initialize the FASTQ validator."""
        super().__init__()
    
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
        
        # Check for empty file
        if os.path.getsize(file_path) == 0:
            return self.format_validation_result(
                valid=False,
                errors={"empty_file": "FASTQ file is empty"}
            )
        
        errors = {}
        warnings = {}
        stats = {}
        
        try:
            # Validate with Rust
            is_valid = fastq_validator.validate_fastq(file_path)
            if not is_valid:
                return self.format_validation_result(
                    valid=False,
                    errors={"invalid_format": "Invalid FASTQ format: header/sequence/quality structure issues"}
                )
            
            # Get statistics from Rust
            stats = fastq_validator.fastq_stats(file_path)
            logger.debug(f"Validated FASTQ file with Rust: {file_path}")
            
        except ValueError as e:
            errors["validation_error"] = f"Validation error: {str(e)}"
            logger.error(f"Rust validation failed: {str(e)}")
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
        
        try:
            # Read the stream into memory for Rust processing
            data = input_stream.read()
            
            # Validate format with Rust
            is_valid = fastq_validator.validate_fastq_from_bytes(data)
            if not is_valid:
                return self.format_validation_result(
                    valid=False,
                    errors={"invalid_format": "Invalid FASTQ format in stream: header/sequence/quality issues"}
                )
            
            # Get statistics from Rust
            stats = fastq_validator.fastq_stats_from_bytes(data)
            logger.debug("Validated FASTQ stream with Rust")
            
            # Try to reset stream position if possible
            try:
                input_stream.seek(0)
            except (AttributeError, IOError):
                warnings["stream_warning"] = "Unable to reset stream position after validation"
                
        except ValueError as e:
            errors["validation_error"] = f"Stream validation error: {str(e)}"
            logger.error(f"Rust stream validation failed: {str(e)}")
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