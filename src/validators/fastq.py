"""
FASTQ file and stream validator with pure Python implementation.
"""
import os
import re
import logging
import io
from typing import Dict, Any, BinaryIO, Tuple, List, Optional

from src.validators.base import BaseValidator

logger = logging.getLogger(__name__)

# Define regex patterns for FASTQ format validation
SEQ_REGEX = re.compile(r'^[A-Za-z.~]+$')
QUAL_REGEX = re.compile(r'^[!-~]+$')

# Patterns for FASTQ readname parsing 
FULL_ILLUMINA_PATTERN = re.compile(r'^@([a-zA-Z\d]+[a-zA-Z\d_-]*):([a-zA-Z\d-]+):([a-zA-Z\d_-]+):(\d+):\d+:\d+:\d+')
SHORT_ILLUMINA_PATTERN = re.compile(r'^@([a-zA-Z\d]+[a-zA-Z\d_-]*):(\d+):\d+:\d+:\d+')

# Instrument ID patterns
NOVASEQ_X_PLUS = re.compile(r'^LH[0-9]{5}$')
NOVASEQ_6000 = re.compile(r'^A[0-9]{5}$')
NOVASEQ_6000_R = re.compile(r'^A[0-9]{5}R$')
HISEQ_X = re.compile(r'^E[0-9]{5}$')
HISEQ_4000 = re.compile(r'^K[0-9]{5}$')
HISEQ_4000_R = re.compile(r'^K[0-9]{5}R$')
HISEQ_3000 = re.compile(r'^J[0-9]{5}$')
HISEQ_2500 = re.compile(r'^D[0-9]{5}$')
HISEQ_2500_HWI = re.compile(r'^HWI-D[0-9]{5}$')
HISEQ_1500 = re.compile(r'^C[0-9]{5}$')
HISEQ_1500_HWI = re.compile(r'^HWI-C[0-9]{5}$')
NEXTSEQ_2000 = re.compile(r'^VH[0-9]{5}$')
NEXTSEQ_550 = re.compile(r'^(NB|NS)55[0-9]{4}$')
NEXTSEQ_500 = re.compile(r'^(NB|NS)50[0-9]{4}$')

def get_instrument_type(machine_id: str) -> Optional[str]:
    """Identify instrument type from machine ID."""
    if NOVASEQ_X_PLUS.match(machine_id):
        return "Illumina NovaSeq X Plus (EFO:0022841)"
    elif NOVASEQ_6000.match(machine_id) or NOVASEQ_6000_R.match(machine_id):
        return "Illumina NovaSeq 6000 (EFO:0008637)"
    elif HISEQ_X.match(machine_id):
        return "Illumina HiSeq X (EFO:0008567)"
    elif HISEQ_4000.match(machine_id) or HISEQ_4000_R.match(machine_id):
        return "Illumina HiSeq 4000 (EFO:0008563)"
    elif HISEQ_3000.match(machine_id):
        return "Illumina HiSeq 3000 (EFO:0008564)"
    elif HISEQ_2500.match(machine_id) or HISEQ_2500_HWI.match(machine_id):
        return "Illumina HiSeq 2500 (EFO:0008565)"
    elif HISEQ_1500.match(machine_id) or HISEQ_1500_HWI.match(machine_id):
        return "Illumina HiSeq 1500 (EFO:0011027)"
    elif NEXTSEQ_2000.match(machine_id):
        return "Illumina NextSeq 2000 (EFO:0010963)"
    elif NEXTSEQ_550.match(machine_id):
        return "Illumina NextSeq 550 (EFO:0008566)"
    elif NEXTSEQ_500.match(machine_id):
        return "Illumina NextSeq 500 (EFO:0009173)"
    else:
        return None

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
    """Validator for FASTQ format files and streams.
    
    This validator uses pure Python implementation for validation.
    It supports both file-based and streaming validation.
    """
    
    def __init__(self):
        """Initialize the FASTQ validator."""
        super().__init__()
        
        # Will store collections from the last validation
        self._last_machine_ids = []
        self._last_flowcells = []
        self._last_lanes = []
        self._last_instrument_types = []
    
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
        
        file_handle = None
        try:
            # Open file for validation
            file_handle = open(file_path, 'rb')
            
            # First validate the format
            validation_result = self.validate_fastq_stream(file_handle)
            
            if not validation_result.valid:
                error_detail = validation_result.error_message
                if validation_result.line_number is not None:
                    error_detail += f" at line {validation_result.line_number}"
                return self.format_validation_result(
                    valid=False,
                    errors={"invalid_format": error_detail}
                )
            
            # Reset file pointer for statistics collection
            file_handle.seek(0)
            
            # Collect statistics
            stats = self.fastq_stats_stream(file_handle)
            
            logger.debug(f"Validated FASTQ file: {file_path}")
            
        except Exception as e:
            errors["validation_error"] = f"Validation error: {str(e)}"
            logger.error(f"Validation failed: {str(e)}")
            return self.format_validation_result(valid=False, errors=errors)
        finally:
            if file_handle:
                try:
                    file_handle.close()
                except:
                    pass
        
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
        
        try:
            # Since we need to read the stream twice and not all streams support seek,
            # we'll buffer the first ~10MB to check format validity
            validation_buffer = io.BytesIO()
            max_validation_size = 10 * 1024 * 1024  # 10MB limit for format validation
            validation_bytes = 0
            
            # Read the first part of the stream for validation only
            while validation_bytes < max_validation_size:
                chunk = input_stream.read(65536)  # 64KB chunks
                if not chunk:
                    break
                    
                validation_buffer.write(chunk)
                validation_bytes += len(chunk)
                
            logger.debug(f"Read {validation_bytes} bytes for initial validation")
            
            # If we couldn't read anything, return empty file error
            if validation_bytes == 0:
                return self.format_validation_result(
                    valid=False,
                    errors={"empty_file": "Stream contained no data"}
                )
                
            # Reset buffer for validation
            validation_buffer.seek(0)
            
            # First validate the format using the buffer
            validation_result = self.validate_fastq_stream(validation_buffer)
            
            if not validation_result.valid:
                error_detail = validation_result.error_message
                if validation_result.line_number is not None:
                    error_detail += f" at line {validation_result.line_number}"
                return self.format_validation_result(
                    valid=False,
                    errors={"invalid_format": error_detail}
                )
            
            # Now we need to read the rest of the stream to get full stats
            # We'll read the stream from the beginning if possible, otherwise
            # we'll use what we already read and continue from there
            try:
                input_stream.seek(0)
                # If seek successful, we can use the original stream for full stats
                stats = self.fastq_stats_stream(input_stream)
            except (AttributeError, IOError) as e:
                warnings["stream_warning"] = "Unable to reset stream position; statistics may be incomplete"
                logger.warning(f"Stream is not seekable: {str(e)}")
                
                # Continue with partial validation using buffer and remaining stream
                validation_buffer.seek(0)
                
                # Create a composite stream from buffer + remaining input
                composite_stream = CompositeStream(validation_buffer, input_stream)
                stats = self.fastq_stats_stream(composite_stream)
            
            # Additional validations
            validation_result = self._perform_additional_validations(stats)
            errors.update(validation_result.get("errors", {}))
            warnings.update(validation_result.get("warnings", {}))
            
            # Determine if valid
            valid = len(errors) == 0
            
            # Try to reset stream one more time for the caller if possible
            try:
                input_stream.seek(0)
            except (AttributeError, IOError) as e:
                warnings["stream_warning"] = f"Unable to reset stream position after validation: {str(e)}"
            
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
    
    def _add_collections_to_stats(self, stats: Dict[str, Any]) -> None:
        """Add the collections data to the stats dictionary."""
        # Add collection data directly from class attributes
        stats["machine_ids"] = self._last_machine_ids
        stats["flowcells"] = self._last_flowcells
        stats["lanes"] = self._last_lanes
        stats["instrument_types"] = self._last_instrument_types
        
        # Add counts to stats
        stats["machine_ids_count"] = len(self._last_machine_ids)
        stats["flowcells_count"] = len(self._last_flowcells)
        stats["lanes_count"] = len(self._last_lanes)
        stats["instrument_types_count"] = len(self._last_instrument_types)

    def validate_fastq_stream(self, stream: BinaryIO) -> FastqValidationResult:
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
                    plus_seqname = plus_line[1:]  # Everything after +
                    header_seqname = current_block[0].decode('utf-8', errors='replace')[1:]  # Everything after @
                    if plus_seqname != header_seqname:
                        return FastqValidationResult.invalid(
                            f"Seqname in + line ('{plus_seqname}') doesn't match header seqname ('{header_seqname}')",
                            line_count - 1
                        )
                
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

    def fastq_stats_stream(self, stream: BinaryIO) -> Dict[str, Any]:
        """
        Calculate statistics for a FASTQ stream.
        
        Args:
            stream: Binary stream containing FASTQ data
            
        Returns:
            Dictionary with statistics including read count, lengths, base counts,
            and any metadata that can be extracted from headers
        """
        read_count = 0
        total_length = 0
        min_length = float('inf')
        max_length = 0
        quality_sum = 0
        current_block = []
        line_count = 0
        
        # Collections for header metadata
        machine_ids = set()
        flowcells = set()
        lanes = set()
        instrument_types = set()
        
        for line in stream:
            line_count += 1
            line = line.rstrip(b'\r\n')
            
            # Add line to current block
            current_block.append(line)
            
            # Process complete blocks (4 lines per FASTQ record)
            if len(current_block) == 4:
                read_count += 1
                
                # Process header for metadata
                header = current_block[0].decode('utf-8', errors='replace')
                
                # Parse readname for full Illumina headers
                type1_match = FULL_ILLUMINA_PATTERN.match(header)
                if type1_match:
                    machine_id = type1_match.group(1)
                    flowcell_id = type1_match.group(3)
                    lane_str = type1_match.group(4)
                    
                    try:
                        lane = int(lane_str)
                        lanes.add(lane)
                    except ValueError:
                        pass
                        
                    machine_ids.add(machine_id)
                    flowcells.add(flowcell_id)
                    
                    # Check for instrument type
                    instr_type = get_instrument_type(machine_id)
                    if instr_type:
                        instrument_types.add(instr_type)
                        
                # Parse readname for partial Illumina headers
                elif SHORT_ILLUMINA_PATTERN.match(header):
                    type2_match = SHORT_ILLUMINA_PATTERN.match(header)
                    machine_id = type2_match.group(1)
                    lane_str = type2_match.group(2)
                    
                    try:
                        lane = int(lane_str)
                        lanes.add(lane)
                    except ValueError:
                        pass
                        
                    machine_ids.add(machine_id)
                    
                    # Check for instrument type
                    instr_type = get_instrument_type(machine_id)
                    if instr_type:
                        instrument_types.add(instr_type)
                
                # Process sequence
                sequence = current_block[1].decode('utf-8', errors='replace')
                seq_length = len(sequence)
                
                # Update length statistics
                total_length += seq_length
                min_length = min(min_length, seq_length)
                max_length = max(max_length, seq_length)
                
                # Process quality line
                quality = current_block[3].decode('utf-8', errors='replace')
                
                # Calculate quality stats (Phred+33 encoded)
                for q in quality:
                    quality_sum += (ord(q) - 33)
                
                # Reset block
                current_block = []
        
        # Prepare stats dictionary
        stats = {}
        
        if read_count > 0:
            # Basic stats
            stats["read_count"] = read_count
            stats["min_length"] = min_length if min_length != float('inf') else 0
            stats["max_length"] = max_length
            stats["total_length"] = total_length
            stats["avg_length"] = total_length / read_count
            
            # Only calculate avg_quality if we have sequences
            if total_length > 0:
                stats["avg_quality"] = quality_sum / total_length
            else:
                stats["avg_quality"] = 0
            
            # Store collection data
            self._last_machine_ids = list(machine_ids)
            self._last_flowcells = list(flowcells)
            self._last_lanes = list(lanes)
            self._last_instrument_types = list(instrument_types)
            
            # Add collection counts to stats
            stats["machine_ids_count"] = len(machine_ids)
            stats["flowcells_count"] = len(flowcells)
            stats["lanes_count"] = len(lanes)
            stats["instrument_types_count"] = len(instrument_types)
            
            # Add collections to stats dictionary
            self._add_collections_to_stats(stats)
        else:
            # Empty or invalid file stats
            stats["read_count"] = 0
            stats["min_length"] = 0
            stats["max_length"] = 0
            stats["total_length"] = 0
            stats["avg_length"] = 0
            stats["avg_quality"] = 0
            
            # Empty collections
            stats["machine_ids_count"] = 0
            stats["flowcells_count"] = 0
            stats["lanes_count"] = 0
            stats["instrument_types_count"] = 0
            
            # Add empty collections to stats
            self._last_machine_ids = []
            self._last_flowcells = []
            self._last_lanes = []
            self._last_instrument_types = []
            self._add_collections_to_stats(stats)
        
        return stats

    def get_last_machine_ids(self) -> str:
        """Get machine IDs from the last validation as a pipe-separated string."""
        return "|".join(self._last_machine_ids)

    def get_last_flowcells(self) -> str:
        """Get flowcells from the last validation as a pipe-separated string."""
        return "|".join(self._last_flowcells)

    def get_last_lanes(self) -> str:
        """Get lanes from the last validation as a pipe-separated string."""
        return "|".join(str(lane) for lane in self._last_lanes)

    def get_last_instrument_types(self) -> str:
        """Get instrument types from the last validation as a pipe-separated string."""
        return "|".join(self._last_instrument_types)

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