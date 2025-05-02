"""
Tests for the FASTQ validator's ability to parse readnames and collect identifiers.

This module tests the FastqValidator's ability to extract and analyze different types
of read identifiers from FASTQ files, including machine IDs, flowcells, and lanes.
"""
import os
import pytest
import tempfile
import io
from pathlib import Path

from src.validators.fastq import FastqValidator

# Get the path to test data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(BASE_DIR, "data", "fastq")


@pytest.fixture
def validator():
    """
    Create a FASTQ validator instance for testing.
    
    Returns:
        FastqValidator: An initialized FASTQ validator
    """
    return FastqValidator()


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory for test files.
    
    Yields:
        str: Path to the temporary directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_type1_readname_parsing(validator, temp_dir):
    """Test parsing Type 1 (full Illumina) readnames."""
    # Create a temporary FASTQ file with Type 1 readnames
    test_file = os.path.join(temp_dir, "type1.fastq")
    with open(test_file, "w") as f:
        f.write("@A00123:456:FLOWCELL1:1:2001:3456:7890\n")
        f.write("ACGTACGT\n")
        f.write("+\n")
        f.write("IIIIIIII\n")
        f.write("@A00456:789:FLOWCELL2:2:2001:5678:9012\n")
        f.write("GCTAGCTA\n")
        f.write("+\n")
        f.write("IIIIIIII\n")
    
    result = validator.validate_file(test_file)
    
    assert result["valid"] is True
    
    # Verify machine identifiers were collected
    assert "machine_ids" in result["stats"]
    assert len(result["stats"]["machine_ids"]) == 2
    assert "A00123" in result["stats"]["machine_ids"]
    assert "A00456" in result["stats"]["machine_ids"]
    
    # Verify flowcells were collected
    assert "flowcells" in result["stats"]
    assert len(result["stats"]["flowcells"]) == 2
    assert "FLOWCELL1" in result["stats"]["flowcells"]
    assert "FLOWCELL2" in result["stats"]["flowcells"]
    
    # Verify lanes were collected
    assert "lanes" in result["stats"]
    assert len(result["stats"]["lanes"]) == 2
    assert 1 in result["stats"]["lanes"]
    assert 2 in result["stats"]["lanes"]


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_type2_readname_parsing(validator, temp_dir):
    """Test parsing Type 2 (partial Illumina) readnames."""
    # Create a temporary FASTQ file with Type 2 readnames
    test_file = os.path.join(temp_dir, "type2.fastq")
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
    
    result = validator.validate_file(test_file)
    
    assert result["valid"] is True
    
    # Verify machine identifiers were collected
    assert "machine_ids" in result["stats"]
    assert len(result["stats"]["machine_ids"]) == 3
    assert "NS500123" in result["stats"]["machine_ids"]
    assert "VH00456" in result["stats"]["machine_ids"]
    assert "E00789" in result["stats"]["machine_ids"]
    
    # Verify flowcells and lanes are empty since Type 2 doesn't have them
    assert "flowcells" in result["stats"]
    assert len(result["stats"]["flowcells"]) == 0
    
    # For Type 2, lanes are still included in the readname
    assert "lanes" in result["stats"]
    assert len(result["stats"]["lanes"]) == 3
    assert 1 in result["stats"]["lanes"]
    assert 2 in result["stats"]["lanes"]
    assert 3 in result["stats"]["lanes"]


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_type3_readname_parsing(validator, temp_dir):
    """Test parsing Type 3 (non-Illumina) readnames."""
    # Create a temporary FASTQ file with Type 3 readnames
    test_file = os.path.join(temp_dir, "type3.fastq")
    with open(test_file, "w") as f:
        f.write("@SRR1234567.1\n")
        f.write("ACGTACGT\n")
        f.write("+\n")
        f.write("IIIIIIII\n")
        f.write("@read_id_123 description\n")
        f.write("GCTAGCTA\n")
        f.write("+\n")
        f.write("IIIIIIII\n")
    
    result = validator.validate_file(test_file)
    
    assert result["valid"] is True
    
    # Verify all collections are empty for Type 3 readnames
    assert "machine_ids" in result["stats"]
    assert len(result["stats"]["machine_ids"]) == 0
    
    assert "flowcells" in result["stats"]
    assert len(result["stats"]["flowcells"]) == 0
    
    assert "lanes" in result["stats"]
    assert len(result["stats"]["lanes"]) == 0


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_mixed_readname_types(validator, temp_dir):
    """Test parsing a mix of different readname types."""
    # Create a temporary FASTQ file with mixed readname types
    test_file = os.path.join(temp_dir, "mixed.fastq")
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
    
    result = validator.validate_file(test_file)
    
    assert result["valid"] is True
    
    # Verify collections contain expected values
    assert "machine_ids" in result["stats"]
    assert len(result["stats"]["machine_ids"]) == 2
    assert "A00123" in result["stats"]["machine_ids"]
    assert "NS500123" in result["stats"]["machine_ids"]
    
    assert "flowcells" in result["stats"]
    assert len(result["stats"]["flowcells"]) == 1
    assert "FLOWCELL1" in result["stats"]["flowcells"]
    
    assert "lanes" in result["stats"]
    assert len(result["stats"]["lanes"]) == 2
    assert 1 in result["stats"]["lanes"]
    assert 2 in result["stats"]["lanes"]


@pytest.mark.skipif(not os.path.exists(TEST_DATA_DIR),
                   reason="Test data directory not found")
def test_instrument_id_matching(validator, temp_dir):
    """Test that machine identifiers match the expected instrument types."""
    # Create a temporary FASTQ file with various instrument IDs
    test_file = os.path.join(temp_dir, "instruments.fastq")
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
    
    result = validator.validate_file(test_file)
    
    assert result["valid"] is True
    
    # Verify instrument_types were collected and matched correctly
    assert "instrument_types" in result["stats"]
    assert len(result["stats"]["instrument_types"]) == 4
    assert "Illumina NovaSeq 6000 (EFO:0008637)" in result["stats"]["instrument_types"]
    assert "Illumina NextSeq 550 (EFO:0008566)" in result["stats"]["instrument_types"]
    assert "Illumina HiSeq 2500 (EFO:0008565)" in result["stats"]["instrument_types"]
    assert "Illumina NovaSeq X Plus (EFO:0022841)" in result["stats"]["instrument_types"] 