"""
Enhanced tests for the FASTQ validator with readname parsing capabilities.
"""
import os
import unittest

from src.validators.fastq import FastqValidator

# Import Rust validator to check availability
try:
    import fastq_validator
    RUST_INSTALLED = True
except ImportError:
    RUST_INSTALLED = False
    print("Rust FASTQ validator is not available - tests cannot proceed")

# Get the path to test data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "data", "fastq")
VALID_FILES_DIR = os.path.join(TEST_DATA_DIR, "valid")

@unittest.skipIf(not RUST_INSTALLED, "Rust FASTQ validator is required for these tests")
class TestFastqValidatorWithReadnames(unittest.TestCase):
    """Test cases for the enhanced FASTQ validator with readname parsing."""
    
    def setUp(self):
        """Set up the test environment."""
        self.validator = FastqValidator()
        
        # Skip tests if test data directory doesn't exist
        if not os.path.exists(TEST_DATA_DIR):
            self.skipTest(f"Test data directory not found: {TEST_DATA_DIR}")
    
    def test_illumina_type1_readnames(self):
        """Test validating a FASTQ file with Type 1 Illumina readnames."""
        file_path = os.path.join(VALID_FILES_DIR, "illumina_type1.fastq")
        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")
        
        result = self.validator.validate_file(file_path)
        
        self.assertTrue(result["valid"])
        
        # Verify machine identifiers were collected
        self.assertIn("machine_ids", result["stats"])
        self.assertEqual(len(result["stats"]["machine_ids"]), 3)
        self.assertIn("A00123", result["stats"]["machine_ids"])
        self.assertIn("K00456", result["stats"]["machine_ids"])
        self.assertIn("LH12345", result["stats"]["machine_ids"])
        
        # Verify flowcells were collected
        self.assertIn("flowcells", result["stats"])
        self.assertEqual(len(result["stats"]["flowcells"]), 3)
        self.assertIn("FLOWCELL1", result["stats"]["flowcells"])
        self.assertIn("FLOWCELL2", result["stats"]["flowcells"])
        self.assertIn("FC123456", result["stats"]["flowcells"])
        
        # Verify lanes were collected
        self.assertIn("lanes", result["stats"])
        self.assertEqual(len(result["stats"]["lanes"]), 3)
        self.assertIn(1, result["stats"]["lanes"])
        self.assertIn(2, result["stats"]["lanes"])
        self.assertIn(3, result["stats"]["lanes"])
        
        # Verify instrument types were identified
        self.assertIn("instrument_types", result["stats"])
        self.assertIn("Illumina NovaSeq 6000 (EFO:0008637)", result["stats"]["instrument_types"])
        self.assertIn("Illumina HiSeq 4000 (EFO:0008563)", result["stats"]["instrument_types"])
        self.assertIn("Illumina NovaSeq X Plus (EFO:0022841)", result["stats"]["instrument_types"])
    
    def test_illumina_type2_readnames(self):
        """Test validating a FASTQ file with Type 2 Illumina readnames."""
        file_path = os.path.join(VALID_FILES_DIR, "illumina_type2.fastq")
        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")
        
        result = self.validator.validate_file(file_path)
        
        self.assertTrue(result["valid"])
        
        # Verify machine identifiers were collected
        self.assertIn("machine_ids", result["stats"])
        self.assertEqual(len(result["stats"]["machine_ids"]), 3)
        self.assertIn("NS500123", result["stats"]["machine_ids"])
        self.assertIn("VH00456", result["stats"]["machine_ids"])
        self.assertIn("E00789", result["stats"]["machine_ids"])
        
        # Verify lanes were collected
        self.assertIn("lanes", result["stats"])
        self.assertEqual(len(result["stats"]["lanes"]), 3)
        self.assertIn(1, result["stats"]["lanes"])
        self.assertIn(2, result["stats"]["lanes"])
        self.assertIn(3, result["stats"]["lanes"])
        
        # Verify instrument types were identified
        self.assertIn("instrument_types", result["stats"])
        self.assertIn("Illumina NextSeq 500 (EFO:0009173)", result["stats"]["instrument_types"])
        self.assertIn("Illumina NextSeq 2000 (EFO:0010963)", result["stats"]["instrument_types"])
        self.assertIn("Illumina HiSeq X (EFO:0008567)", result["stats"]["instrument_types"])
    
    def test_non_illumina_readnames(self):
        """Test validating a FASTQ file with non-Illumina readnames."""
        file_path = os.path.join(VALID_FILES_DIR, "non_illumina.fastq")
        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")
        
        result = self.validator.validate_file(file_path)
        
        self.assertTrue(result["valid"])
        
        # Verify no machine identifiers, flowcells, or lanes were collected
        self.assertIn("machine_ids", result["stats"])
        self.assertEqual(len(result["stats"]["machine_ids"]), 0)
        
        self.assertIn("flowcells", result["stats"])
        self.assertEqual(len(result["stats"]["flowcells"]), 0)
        
        self.assertIn("lanes", result["stats"])
        self.assertEqual(len(result["stats"]["lanes"]), 0)
        
        # Verify no instrument types were identified
        self.assertIn("instrument_types", result["stats"])
        self.assertEqual(len(result["stats"]["instrument_types"]), 0)


if __name__ == "__main__":
    unittest.main() 