"""
Module for collecting statistics from FASTQ files.
"""

from typing import Dict, Any

class FastqStatistics:
    """
    Collector for FASTQ file and read statistics.
    
    Tracks information such as read count, sequence lengths, quality scores,
    and aggregates metadata from FASTQ headers.
    """
    
    def __init__(self):
        """Initialize the statistics collector."""
        self.reset()
    
    def reset(self) -> None:
        """Reset all statistics to initial values."""
        self.read_count = 0
        self.total_length = 0
        self.min_length = float('inf')
        self.max_length = 0
        self.quality_sum = 0
        self.avg_length = 0
        self.avg_quality = 0
    
    def update_sequence_stats(self, sequence: str, quality: str) -> None:
        """
        Update statistics based on a sequence and quality string.
        
        Args:
            sequence: The nucleotide sequence
            quality: The quality score string
        """
        self.read_count += 1
        
        # Process sequence
        seq_length = len(sequence)
        self.total_length += seq_length
        self.min_length = min(self.min_length, seq_length)
        self.max_length = max(self.max_length, seq_length)
        
        # Calculate quality stats (Phred+33 encoded)
        for q in quality:
            self.quality_sum += (ord(q) - 33)
        
        # Update averages
        if self.read_count > 0:
            self.avg_length = self.total_length / self.read_count
            if self.total_length > 0:
                self.avg_quality = self.quality_sum / self.total_length
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get all collected statistics.
        
        Returns:
            Dictionary with all collected statistics
        """
        stats = {}
        
        if self.read_count > 0:
            # Basic stats
            stats["read_count"] = self.read_count
            stats["min_length"] = self.min_length if self.min_length != float('inf') else 0
            stats["max_length"] = self.max_length
            stats["total_length"] = self.total_length
            stats["avg_length"] = self.avg_length
            stats["avg_quality"] = self.avg_quality
            # Expose read_length for downstream patching as the average read length
            stats["read_length"] = self.avg_length
        else:
            # Empty or invalid file stats
            stats["read_count"] = 0
            stats["min_length"] = 0
            stats["max_length"] = 0
            stats["total_length"] = 0
            stats["avg_length"] = 0
            stats["avg_quality"] = 0
            # When no reads are present, set read_length to 0 to mirror avg_length
            stats["read_length"] = 0
        
        return stats
    
    def validate_statistics(self) -> Dict[str, Dict[str, str]]:
        """
        Validate collected statistics and identify potential issues.
        
        Returns:
            Dictionary with errors and warnings
        """
        errors = {}
        warnings = {}
        
        # Check if file is empty
        if self.read_count == 0:
            errors["empty_file"] = "FASTQ data contains no sequences"
            return {"errors": errors, "warnings": warnings}
        
        # Check for unusually short reads
        if self.min_length < 10:
            warnings["short_reads"] = f"Data contains very short reads (minimum length: {self.min_length})"
        
        # Check read length variability
        if self.max_length > 0 and self.min_length > 0 and (self.max_length - self.min_length) > 0.5 * self.avg_length:
            warnings["variable_length"] = f"Read lengths are highly variable (min: {self.min_length}, max: {self.max_length})"
        
        # Check for unusually small total sequence volume
        if self.total_length < 1000 and self.read_count > 0:
            warnings["low_sequence_volume"] = f"Total sequence volume is very small: {self.total_length} bp"
        
        return {"errors": errors, "warnings": warnings} 