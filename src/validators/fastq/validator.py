"""
Core FASTQ validator implementation.
"""

import os
import re
import logging
import io
import gzip
from typing import Dict, Any, BinaryIO, Optional, Tuple

from src.validators.base import BaseValidator, HashCalculatingStream
from src.validators.fastq.parser import FastqHeaderParser
from src.validators.fastq.statistics import FastqStatistics
from src.utils.helpers import has_gz_extension

logger = logging.getLogger(__name__)

# Define regex patterns for FASTQ format validation
SEQ_REGEX = re.compile(r'^[A-Za-z.~]+$')
QUAL_REGEX = re.compile(r'^[\x21-\x7E]+$')  # ASCII 33-126, from '!' to '~'

class FastqValidationResult:
    """Result of FASTQ validation with detailed error information."""
    
    def __init__(self, valid: bool, error_message: Optional[str] = None, line_number: Optional[int] = None):
        self.valid = valid
        self.error_message = error_message
        self.line_number = line_number

    @classmethod
    def valid(cls):
        """Create a valid result."""
        return cls(True)
        
    @classmethod
    def invalid(cls, error_message: str, line_number: int):
        """Create an invalid result with error details."""
        return cls(False, error_message, line_number)

class FastqValidator(BaseValidator):
    """
    Validator for FASTQ format files and streams.
    
    This validator uses pure Python implementation for validation.
    It supports both file-based and streaming validation.
    """
    
    def __init__(self):
        """Initialize the FASTQ validator."""
        super().__init__()
        self.header_parser = FastqHeaderParser()
        self.statistics = FastqStatistics()
        self.mismatched_ids = {}
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a FASTQ file.
        
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
        
        file_handle = None
        try:
            # Reset collectors
            self.header_parser.reset()
            self.statistics.reset()
            self.mismatched_ids = {}
            
            # Check if file is gzipped
            is_gzipped = has_gz_extension(file_path)
            
            # For gzipped files, we'll use gzip.open
            if is_gzipped:
                with gzip.open(file_path, 'rb') as f:
                    # Read the entire content
                    content = f.read()
                    # Use a BytesIO buffer for validation
                    validation_stream = io.BytesIO(content)
                    # Create a separate stream for hash calculation
                    hash_stream_source = io.BytesIO(content)
                    # Calculate hashes on the original compressed data
                    with open(file_path, 'rb') as raw_file:
                        hash_stream, metadata = self.create_hash_calculating_stream(raw_file, is_gzipped=True)
                        # Read the stream to calculate hashes
                        while hash_stream.read(8192):
                            pass
                    # Validate the content
                    validation_result = self.validate_fastq_stream(validation_stream, collect_stats=True)
            else:
                # For uncompressed files
                with open(file_path, 'rb') as f:
                    # Read the entire content
                    content = f.read()
                    # Use a BytesIO buffer for both validation and hash calculation
                    validation_stream = io.BytesIO(content)
                    hash_stream_source = io.BytesIO(content)
                    # Calculate hashes
                    hash_stream, metadata = self.create_hash_calculating_stream(hash_stream_source, is_gzipped=False)
                    # Read the stream to calculate hashes
                    while hash_stream.read(8192):
                        pass
                    # Validate the content
                    validation_result = self.validate_fastq_stream(validation_stream, collect_stats=True)
            
            if not validation_result.valid:
                error_detail = validation_result.error_message
                if validation_result.line_number is not None:
                    error_detail += f" at line {validation_result.line_number}"
                return self.format_validation_result(
                    valid=False,
                    errors={"invalid_format": error_detail}
                )
            
            # Get hash values from the stream
            hash_stats = self.get_hash_values(hash_stream, metadata)
            
            logger.debug(f"Validated FASTQ file: {file_path}")
            
        except Exception as e:
            errors["validation_error"] = f"Validation error: {str(e)}"
            logger.error(f"Validation failed: {str(e)}")
            return self.format_validation_result(valid=False, errors=errors)
        
        # Get statistics
        stats = self.statistics.get_statistics()
        
        # Add hash values to stats
        stats.update(hash_stats)
        
        # Add metadata from header parser
        stats.update(self.header_parser.get_formatted_metadata())
        
        # Additional validations and quality checks based on stats
        validation_result = self.statistics.validate_statistics()
        errors.update(validation_result.get("errors", {}))
        warnings.update(validation_result.get("warnings", {}))
        
        # Add mismatched IDs to errors instead of warnings
        if self.mismatched_ids:
            errors["mismatched_ids"] = f"Found {len(self.mismatched_ids)} records with mismatched IDs in header and description lines"
        
        # Determine if valid (no errors, even if there are warnings)
        valid = len(errors) == 0
        
        return self.format_validation_result(
            valid=valid,
            errors=errors,
            warnings=warnings,
            stats=stats
        )
    
    def validate_stream(self, input_stream: BinaryIO, is_gzipped: bool = False) -> Dict[str, Any]:
        """
        Validate a FASTQ data stream.
        
        Args:
            input_stream: Binary stream containing FASTQ data
            is_gzipped: Whether the stream contains gzipped data
            
        Returns:
            Dictionary with validation results
        """
        errors = {}
        warnings = {}
        
        try:
            # Reset collectors
            self.header_parser.reset()
            self.statistics.reset()
            self.mismatched_ids = {}
            
            # Always read the entire content into memory
            # This ensures we can use it for both validation and hash calculation
            if hasattr(input_stream, 'read'):
                content = input_stream.read()
            else:
                content = input_stream
            
            # Create two copies of the data
            hash_stream_source = io.BytesIO(content)
            
            # Create hash calculating stream wrapper for hashes of compressed data
            hash_stream, metadata = self.create_hash_calculating_stream(hash_stream_source, is_gzipped)
            
            # Read the hash stream to calculate hash values
            while hash_stream.read(8192):
                pass
                
            # Get hash values from the stream
            hash_stats = self.get_hash_values(hash_stream, metadata)
            
            # If content is gzipped, we need to decompress it for validation
            if is_gzipped:
                try:
                    # Decompress the content
                    decompressed_content = gzip.decompress(content)
                    validation_stream = io.BytesIO(decompressed_content)
                except Exception as e:
                    logger.error(f"Error decompressing content: {e}")
                    return self.format_validation_result(
                        valid=False,
                        errors={"decompression_error": f"Failed to decompress gzipped content: {str(e)}"}
                    )
            else:
                validation_stream = io.BytesIO(content)
            
            # Use the separate validation stream for format validation
            # Always collect statistics during validation
            validation_result = self.validate_fastq_stream(validation_stream, collect_stats=True)
            
            if not validation_result.valid:
                error_detail = validation_result.error_message
                if validation_result.line_number is not None:
                    error_detail += f" at line {validation_result.line_number}"
                return self.format_validation_result(
                    valid=False,
                    errors={"invalid_format": error_detail}
                )
            
            # Get statistics and metadata
            stats = self.statistics.get_statistics()
            
            # Add hash values to stats
            stats.update(hash_stats)
            
            # Add metadata from header parser
            stats.update(self.header_parser.get_formatted_metadata())
            
            # Additional validations
            validation_result = self.statistics.validate_statistics()
            errors.update(validation_result.get("errors", {}))
            warnings.update(validation_result.get("warnings", {}))
            
            # Add mismatched IDs to errors
            if self.mismatched_ids:
                errors["mismatched_ids"] = f"Found {len(self.mismatched_ids)} records with mismatched IDs"
            
            # Determine if valid
            valid = len(errors) == 0
            
            return self.format_validation_result(
                valid=valid,
                errors=errors,
                warnings=warnings,
                stats=stats
            )
            
        except Exception as e:
            logger.error(f"Stream validation error: {str(e)}")
            return self.format_validation_result(
                valid=False, 
                errors={"stream_error": f"Stream validation error: {str(e)}"}
            )

    def validate_fastq_stream(self, stream: BinaryIO, collect_stats: bool = False) -> FastqValidationResult:
        """
        Validate a FASTQ input stream for correct format.
        
        This function checks:
        1. Every block starts with @ (header)
        2. Sequence line contains only valid sequence characters
        3. + line follows the sequence, with optional matching seqname
        4. Quality line contains valid quality characters
        5. Sequence and quality lines have equal length
        
        Args:
            stream: Binary stream to validate
            collect_stats: Whether to collect statistics during validation
            
        Returns:
            FastqValidationResult with validation result and error details if invalid
        """
        line_count = 0
        current_block = []
        
        for line in stream:
            line_count += 1
            line = line.rstrip(b'\r\n')
            
            # Add line to current block
            current_block.append(line)
            
            # Process complete blocks (4 lines per FASTQ record)
            if len(current_block) == 4:
                # 1. Check header line starts with @
                if not current_block[0].startswith(b'@'):
                    return FastqValidationResult.invalid(
                        f"Header line must start with @: '{current_block[0].decode('utf-8', errors='replace')}'",
                        line_count - 3
                    )
                
                # 2. Validate sequence characters
                seq_line = current_block[1].decode('utf-8', errors='replace')
                if not SEQ_REGEX.match(seq_line):
                    return FastqValidationResult.invalid(
                        f"Invalid sequence characters: '{seq_line}'",
                        line_count - 2
                    )
                
                # 3. Check + line format
                plus_line = current_block[2].decode('utf-8', errors='replace')
                if not plus_line.startswith('+'):
                    return FastqValidationResult.invalid(
                        f"Quality header must start with +: '{plus_line}'",
                        line_count - 1
                    )
                
                # If + is followed by a seqname, check it matches the header seqname exactly
                if len(plus_line) > 1:
                    plus_seqname = plus_line[1:].split(' ')[0]  # Everything after + before first space
                    header_line = current_block[0].decode('utf-8', errors='replace')
                    header_seqname = header_line[1:].split(' ')[0]  # Everything after @ before first space
                    
                    # Check for ID mismatch (part before first space)
                    if plus_seqname != header_seqname:
                        # Store the mismatch info for later warning creation
                        if not hasattr(self, 'mismatched_ids'):
                            self.mismatched_ids = {}
                        self.mismatched_ids[line_count - 1] = {
                            'header_id': header_seqname,
                            'plus_id': plus_seqname
                        }
                    # Also check if entire description after + differs from header description
                    elif len(plus_line) > 1 and len(header_line) > 1:
                        plus_desc = plus_line[1:]  # Full description after +
                        header_desc = header_line[1:]  # Full description after @
                        
                        if plus_desc != header_desc:
                            # IDs match but descriptions differ
                            if not hasattr(self, 'mismatched_ids'):
                                self.mismatched_ids = {}
                            self.mismatched_ids[line_count - 1] = {
                                'header_desc': header_desc,
                                'plus_desc': plus_desc,
                                'desc_mismatch': True
                            }
                
                # 4. Validate quality characters
                qual_line = current_block[3].decode('utf-8', errors='replace')
                if not QUAL_REGEX.match(qual_line):
                    return FastqValidationResult.invalid(
                        f"Invalid quality characters: '{qual_line}'",
                        line_count
                    )
                
                # 5. Check sequence and quality line lengths match
                if len(seq_line) != len(qual_line):
                    return FastqValidationResult.invalid(
                        f"Sequence length ({len(seq_line)}) and quality length ({len(qual_line)}) don't match",
                        line_count
                    )
                
                # 6. Check for valid quality values (ASCII 33-126)
                for i, c in enumerate(qual_line):
                    ascii_val = ord(c)
                    if ascii_val < 33 or ascii_val > 126:
                        return FastqValidationResult.invalid(
                            f"Invalid quality value at position {i + 1}: ASCII {ascii_val}",
                            line_count
                        )
                
                # 7. If collecting stats, process this record for statistics and metadata
                if collect_stats:
                    header = current_block[0].decode('utf-8', errors='replace')
                    self.header_parser.parse_header(header)
                    self.statistics.update_sequence_stats(seq_line, qual_line)
                
                # Reset for next block
                current_block = []
        
        # A valid FASTQ file should have at least one block
        if line_count == 0:
            return FastqValidationResult.invalid(
                "Empty FASTQ file",
                0
            )
        
        # Check if file has a complete number of blocks
        if len(current_block) != 0:
            return FastqValidationResult.invalid(
                f"Incomplete FASTQ block. Line count ({line_count}) is not a multiple of 4",
                line_count
            )
        
        return FastqValidationResult.valid()

    def _process_fastq_content(self, stream: BinaryIO) -> None:
        """
        Process FASTQ content to extract statistics and metadata.
        
        This method reads through a FASTQ file, updating statistics and
        extracting metadata from headers.
        
        Args:
            stream: Binary stream containing FASTQ data
        """
        current_block = []
        
        for line in stream:
            line = line.rstrip(b'\r\n')
            
            # Add line to current block
            current_block.append(line)
            
            # Process complete blocks (4 lines per FASTQ record)
            if len(current_block) == 4:
                # Process header for metadata
                header = current_block[0].decode('utf-8', errors='replace')
                self.header_parser.parse_header(header)
                
                # Process sequence and quality for statistics
                sequence = current_block[1].decode('utf-8', errors='replace')
                quality = current_block[3].decode('utf-8', errors='replace')
                self.statistics.update_sequence_stats(sequence, quality)
                
                # Reset block
                current_block = []

    def get_last_machine_ids(self) -> str:
        """Get machine IDs from the last validation as a pipe-separated string."""
        return "|".join(self.header_parser.machine_ids)

    def get_last_flowcells(self) -> str:
        """Get flowcells from the last validation as a pipe-separated string."""
        return "|".join(self.header_parser.flowcells)

    def get_last_lanes(self) -> str:
        """Get lanes from the last validation as a pipe-separated string."""
        return "|".join(str(lane) for lane in self.header_parser.lanes)

    def get_last_instrument_types(self) -> str:
        """Get instrument types from the last validation as a pipe-separated string."""
        return "|".join(self.header_parser.instrument_types)

# Helper class for concatenating streams
class CompositeStream:
    """A stream that concatenates multiple streams."""
    
    def __init__(self, *streams):
        self.streams = list(streams)
        self.current_stream_index = 0
    
    def read(self, size=-1):
        if self.current_stream_index >= len(self.streams):
            return b''
            
        data = self.streams[self.current_stream_index].read(size)
        
        # If we've reached the end of the current stream, move to the next one
        if not data and self.current_stream_index < len(self.streams) - 1:
            self.current_stream_index += 1
            return self.read(size)
            
        return data 