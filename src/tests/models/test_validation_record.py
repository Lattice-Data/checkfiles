import json
import pytest
from src.models.validation_record import FileValidationRecord

def test_validation_record_creation():
    """Test basic creation of a FileValidationRecord."""
    record = FileValidationRecord("test.fastq", "test-uuid", "etag123")
    
    # Check initial values
    assert record.file_path == "test.fastq"
    assert record.uuid == "test-uuid"
    assert record.original_etag == "etag123"
    assert record.validation_success is None
    assert record.info == {}
    assert record.errors == {}
    assert record.file_not_found is False

def test_update_info():
    """Test updating info in a FileValidationRecord."""
    record = FileValidationRecord("test.fastq")
    
    # Test empty update
    record.update_info({})
    assert record.info == {}
    
    # Test basic update
    record.update_info({"read_count": 1000})
    assert record.info == {"read_count": 1000}
    
    # Test additional update
    record.update_info({"md5sum": "abcdef"})
    assert record.info == {"read_count": 1000, "md5sum": "abcdef"}
    
    # Test override
    record.update_info({"read_count": 2000})
    assert record.info == {"read_count": 2000, "md5sum": "abcdef"}

def test_update_errors():
    """Test updating errors in a FileValidationRecord."""
    record = FileValidationRecord("test.fastq")
    
    # Test empty update
    record.update_errors({})
    assert record.errors == {}
    
    # Test error update
    record.update_errors({"format_error": "Invalid format"})
    assert record.errors == {"format_error": "Invalid format"}
    
    # Test additional error
    record.update_errors({"md5_error": "MD5 mismatch"})
    assert record.errors == {"format_error": "Invalid format", "md5_error": "MD5 mismatch"}

def test_make_payload():
    """Test generating a payload from a FileValidationRecord."""
    record = FileValidationRecord("test.fastq")
    
    # Add some info
    record.update_info({"read_count": 1000, "md5sum": "abcdef"})
    
    # Set validation success
    record.validation_success = True
    
    # Generate payload
    payload = json.loads(record.make_payload())
    
    # Check payload contents
    assert payload["read_count"] == 1000
    assert payload["md5sum"] == "abcdef"
    assert payload["validated"] is True
    
    # Test with no validation status
    record.validation_success = None
    payload = json.loads(record.make_payload())
    assert "validated" not in payload
