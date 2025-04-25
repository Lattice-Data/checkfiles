"""
Tests for the FASTQ validator's ability to parse readnames and collect identifiers.
"""
import os
import unittest
import tempfile
import io

from src.validators.fastq import FastqValidator

# Get the path to test data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "data", "fastq")

class TestFastqReadnameParser(unittest.TestCase):
    """Test cases for the FASTQ validator's readname parsing functionality."""
    
    def setUp(self):
        """Set up the test environment."""
        self.validator = FastqValidator()
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Skip tests if test data directory doesn't exist
        if not os.path.exists(TEST_DATA_DIR):
            self.skipTest(f"Test data directory not found: {TEST_DATA_DIR}")
            
    def tearDown(self):
        """Clean up after the tests."""
        self.temp_dir.cleanup()
    
    def test_type1_readname_parsing(self):
        """Test parsing Type 1 (full Illumina) readnames."""
        # Create a temporary FASTQ file with Type 1 readnames
        test_file = os.path.join(self.temp_dir.name, "type1.fastq")
        with open(test_file, "w") as f:
            f.write("@A00123:456:FLOWCELL1:1:2001:3456:7890\n")
            f.write("ACGTACGT\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            f.write("@A00456:789:FLOWCELL2:2:2001:5678:9012\n")
            f.write("GCTAGCTA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
        
        result = self.validator.validate_file(test_file)
        
        self.assertTrue(result["valid"])
        
        # Verify machine identifiers were collected
        self.assertIn("machine_ids", result["stats"])
        self.assertEqual(len(result["stats"]["machine_ids"]), 2)
        self.assertIn("A00123", result["stats"]["machine_ids"])
        self.assertIn("A00456", result["stats"]["machine_ids"])
        
        # Verify flowcells were collected
        self.assertIn("flowcells", result["stats"])
        self.assertEqual(len(result["stats"]["flowcells"]), 2)
        self.assertIn("FLOWCELL1", result["stats"]["flowcells"])
        self.assertIn("FLOWCELL2", result["stats"]["flowcells"])
        
        # Verify lanes were collected
        self.assertIn("lanes", result["stats"])
        self.assertEqual(len(result["stats"]["lanes"]), 2)
        self.assertIn(1, result["stats"]["lanes"])
        self.assertIn(2, result["stats"]["lanes"])
    
    def test_type2_readname_parsing(self):
        """Test parsing Type 2 (partial Illumina) readnames."""
        # Create a temporary FASTQ file with Type 2 readnames
        test_file = os.path.join(self.temp_dir.name, "type2.fastq")
        with open(test_file, "w") as f:
            f.write("@NS500123:1:2001:3456:7890\n")
            f.write("ACGTACGTACGTACGTACGTACGTACGTACGT\n")
            f.write("+\n")
            f.write("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")
            f.write("@VH00456:2:2001:5678:9012\n")
            f.write("GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA\n")
            f.write("+\n")
            f.write("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")
            f.write("@E00789:3:1101:1234:5678\n")
            f.write("TGCATGCATGCATGCATGCATGCATGCATGCA\n")
            f.write("+\n")
            f.write("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")
        
        result = self.validator.validate_file(test_file)
        
        self.assertTrue(result["valid"])
        
        # Verify machine identifiers were collected
        self.assertIn("machine_ids", result["stats"])
        self.assertEqual(len(result["stats"]["machine_ids"]), 3)
        self.assertIn("NS500123", result["stats"]["machine_ids"])
        self.assertIn("VH00456", result["stats"]["machine_ids"])
        self.assertIn("E00789", result["stats"]["machine_ids"])
        
        # Verify flowcells and lanes are empty since Type 2 doesn't have them
        self.assertIn("flowcells", result["stats"])
        self.assertEqual(len(result["stats"]["flowcells"]), 0)
        
        # For Type 2, lanes are still included in the readname
        self.assertIn("lanes", result["stats"])
        self.assertEqual(len(result["stats"]["lanes"]), 3)
        self.assertIn(1, result["stats"]["lanes"])
        self.assertIn(2, result["stats"]["lanes"])
        self.assertIn(3, result["stats"]["lanes"])
    
    def test_type3_readname_parsing(self):
        """Test parsing Type 3 (non-Illumina) readnames."""
        # Create a temporary FASTQ file with Type 3 readnames
        test_file = os.path.join(self.temp_dir.name, "type3.fastq")
        with open(test_file, "w") as f:
            f.write("@SRR1234567.1\n")
            f.write("ACGTACGT\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            f.write("@read_id_123 description\n")
            f.write("GCTAGCTA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
        
        result = self.validator.validate_file(test_file)
        
        self.assertTrue(result["valid"])
        
        # Verify all collections are empty for Type 3 readnames
        self.assertIn("machine_ids", result["stats"])
        self.assertEqual(len(result["stats"]["machine_ids"]), 0)
        
        self.assertIn("flowcells", result["stats"])
        self.assertEqual(len(result["stats"]["flowcells"]), 0)
        
        self.assertIn("lanes", result["stats"])
        self.assertEqual(len(result["stats"]["lanes"]), 0)
    
    def test_mixed_readname_types(self):
        """Test parsing a mix of different readname types."""
        # Create a temporary FASTQ file with mixed readname types
        test_file = os.path.join(self.temp_dir.name, "mixed.fastq")
        with open(test_file, "w") as f:
            # Type 1
            f.write("@A00123:456:FLOWCELL1:1:2001:3456:7890\n")
            f.write("ACGTACGT\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            # Type 2
            f.write("@NS500123:2:2001:5678:9012\n")
            f.write("GCTAGCTA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            # Type 3
            f.write("@SRR1234567.1\n")
            f.write("TGCATGCA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
        
        result = self.validator.validate_file(test_file)
        
        self.assertTrue(result["valid"])
        
        # Verify collections contain expected values
        self.assertIn("machine_ids", result["stats"])
        self.assertEqual(len(result["stats"]["machine_ids"]), 2)
        self.assertIn("A00123", result["stats"]["machine_ids"])
        self.assertIn("NS500123", result["stats"]["machine_ids"])
        
        self.assertIn("flowcells", result["stats"])
        self.assertEqual(len(result["stats"]["flowcells"]), 1)
        self.assertIn("FLOWCELL1", result["stats"]["flowcells"])
        
        self.assertIn("lanes", result["stats"])
        self.assertEqual(len(result["stats"]["lanes"]), 2)
        self.assertIn(1, result["stats"]["lanes"])
        self.assertIn(2, result["stats"]["lanes"])
    
    def test_instrument_id_matching(self):
        """Test that machine identifiers match the expected instrument types."""
        # Create a temporary FASTQ file with various instrument IDs
        test_file = os.path.join(self.temp_dir.name, "instruments.fastq")
        with open(test_file, "w") as f:
            # NovaSeq 6000
            f.write("@A00123:456:FLOWCELL1:1:2001:3456:7890\n")
            f.write("ACGTACGT\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            # NextSeq 550
            f.write("@NB551234:2:2001:5678:9012\n")
            f.write("GCTAGCTA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            # HiSeq 2500
            f.write("@D00123:789:FLOWCELL3:3:2001:1234:5678\n")
            f.write("TGCATGCA\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
            # NovaSeq X Plus
            f.write("@LH12345:987:FLOWCELL4:4:2001:9876:5432\n")
            f.write("AATTCCGG\n")
            f.write("+\n")
            f.write("IIIIIIII\n")
        
        result = self.validator.validate_file(test_file)
        
        self.assertTrue(result["valid"])
        
        # Verify instrument_types were collected and matched correctly
        self.assertIn("instrument_types", result["stats"])
        self.assertEqual(len(result["stats"]["instrument_types"]), 4)
        self.assertIn("Illumina NovaSeq 6000 (EFO:0008637)", result["stats"]["instrument_types"])
        self.assertIn("Illumina NextSeq 550 (EFO:0008566)", result["stats"]["instrument_types"])
        self.assertIn("Illumina HiSeq 2500 (EFO:0008565)", result["stats"]["instrument_types"])
        self.assertIn("Illumina NovaSeq X Plus (EFO:0022841)", result["stats"]["instrument_types"])


if __name__ == "__main__":
    unittest.main() 