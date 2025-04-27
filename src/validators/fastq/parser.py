"""
Module for parsing FASTQ header formats and extracting metadata.
"""

import re
from typing import Dict, Optional, Set, Tuple, Union

from src.validators.fastq.instruments import get_instrument_type

# Define regex patterns for FASTQ readname parsing
FULL_ILLUMINA_PATTERN = re.compile(r'^@([a-zA-Z\d]+[a-zA-Z\d_-]*):([a-zA-Z\d-]+):([a-zA-Z\d_-]+):(\d+):\d+:\d+:\d+')
SHORT_ILLUMINA_PATTERN = re.compile(r'^@([a-zA-Z\d]+[a-zA-Z\d_-]*):(\d+):\d+:\d+:\d+')

class FastqHeaderParser:
    """
    Parser for FASTQ headers to extract read information and instrument metadata.
    
    This handles different Illumina header formats and extracts machine IDs,
    flowcell IDs, lane numbers, and maps machine IDs to instrument types.
    """
    
    def __init__(self):
        """Initialize the header parser."""
        # Collections for header metadata
        self.reset()
    
    def reset(self) -> None:
        """Reset all collected metadata."""
        self.machine_ids: Set[str] = set()
        self.flowcells: Set[str] = set()
        self.lanes: Set[int] = set()
        self.instrument_types: Set[str] = set()
    
    def parse_header(self, header: str) -> Dict[str, Optional[str]]:
        """
        Parse a FASTQ header line to extract metadata.
        
        Args:
            header: The FASTQ header line (starting with @)
            
        Returns:
            Dictionary with extracted metadata fields
        """
        result = {
            'machine_id': None,
            'flowcell_id': None,
            'lane': None,
            'instrument_type': None
        }
        
        # Parse readname for full Illumina headers (type 1)
        type1_match = FULL_ILLUMINA_PATTERN.match(header)
        if type1_match:
            machine_id = type1_match.group(1)
            flowcell_id = type1_match.group(3)
            lane_str = type1_match.group(4)
            
            result['machine_id'] = machine_id
            result['flowcell_id'] = flowcell_id
            
            try:
                lane = int(lane_str)
                result['lane'] = lane
                self.lanes.add(lane)
            except ValueError:
                pass
                
            self.machine_ids.add(machine_id)
            self.flowcells.add(flowcell_id)
            
            # Check for instrument type
            instr_type = get_instrument_type(machine_id)
            if instr_type:
                result['instrument_type'] = instr_type
                self.instrument_types.add(instr_type)
                
        # Parse readname for partial Illumina headers (type 2)
        elif SHORT_ILLUMINA_PATTERN.match(header):
            type2_match = SHORT_ILLUMINA_PATTERN.match(header)
            machine_id = type2_match.group(1)
            lane_str = type2_match.group(2)
            
            result['machine_id'] = machine_id
            
            try:
                lane = int(lane_str)
                result['lane'] = lane
                self.lanes.add(lane)
            except ValueError:
                pass
                
            self.machine_ids.add(machine_id)
            
            # Check for instrument type
            instr_type = get_instrument_type(machine_id)
            if instr_type:
                result['instrument_type'] = instr_type
                self.instrument_types.add(instr_type)
        
        return result
    
    def get_metadata_counts(self) -> Dict[str, int]:
        """
        Get counts of collected metadata types.
        
        Returns:
            Dictionary with counts for each metadata type
        """
        return {
            "machine_ids_count": len(self.machine_ids),
            "flowcells_count": len(self.flowcells),
            "lanes_count": len(self.lanes),
            "instrument_types_count": len(self.instrument_types)
        }
    
    def get_metadata_lists(self) -> Dict[str, list]:
        """
        Get lists of collected metadata.
        
        Returns:
            Dictionary with lists of each metadata type
        """
        return {
            "machine_ids": list(self.machine_ids),
            "flowcells": list(self.flowcells),
            "lanes": list(self.lanes),
            "instrument_types": list(self.instrument_types)
        }
    
    def get_formatted_metadata(self) -> Dict[str, Union[str, list, int]]:
        """
        Get all metadata in a standardized format suitable for validation results.
        
        Returns:
            Dictionary with metadata lists and counts
        """
        metadata = {}
        
        # Add collections as lists
        metadata.update(self.get_metadata_lists())
        
        # Add counts
        metadata.update(self.get_metadata_counts())
        
        return metadata 