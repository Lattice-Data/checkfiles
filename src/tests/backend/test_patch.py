import pytest
import requests
import json
from unittest.mock import patch, MagicMock

from src.models.validation_record import FileValidationRecord
from src.backend.patch import fetch_etag_for_uuid, compare_with_db, patch_file

@pytest.fixture
def validation_record():
    """Create a sample validation record for testing."""
    record = FileValidationRecord("test.fastq", "test-uuid", "test-etag")
    record.validation_success = True
    record.update_info({
        "read_count": 1000,
        "md5sum": "abcdef",
        "flowcell_details": [{"machine": "MACHINE1", "flowcell": "FLOW1", "lane": "1"}]
    })
    return record

@pytest.fixture
def file_metadata():
    """Create sample file metadata for testing."""
    return {
        "uuid": "test-uuid",
        "read_count": 500,  # Different from validation record
        "md5sum": "abcdef",  # Same as validation record
        "flowcell_details": [{"machine": "MACHINE1", "flowcell": "FLOW1", "lane": "1"}]
    }

@pytest.fixture
def schema_properties():
    """Create sample schema properties for testing."""
    return {
        "read_count": {"type": "integer"},
        "md5sum": {"type": "string"},
        "flowcell_details": {"type": "array"},
        "validated": {"type": "boolean"}
    }

def test_fetch_etag_success(requests_mock):
    """Test fetching an ETag successfully."""
    requests_mock.get(
        "https://example.com/test-uuid?frame=edit&datastore=database",
        headers={"etag": "test-etag"}
    )
    
    etag = fetch_etag_for_uuid("https://example.com", "test-uuid", ("key", "secret"))
    assert etag == "test-etag"

def test_fetch_etag_failure(requests_mock):
    """Test handling of ETag fetch failure."""
    requests_mock.get(
        "https://example.com/test-uuid?frame=edit&datastore=database",
        status_code=404
    )
    
    etag = fetch_etag_for_uuid("https://example.com", "test-uuid", ("key", "secret"))
    assert etag is None

def test_compare_with_db(validation_record, file_metadata, schema_properties):
    """Test comparison between validation record and DB metadata."""
    result = compare_with_db(validation_record, file_metadata, schema_properties)
    
    # Check that post_json contains read_count (different value)
    assert "post_json" in result
    assert "read_count" in result["post_json"]
    assert result["post_json"]["read_count"] == 1000
    
    # Check that post_json does not contain md5sum (same value)
    assert "md5sum" not in result["post_json"]
    
    # Check validation status is included
    assert "validated" in result["post_json"]
    assert result["post_json"]["validated"] is True
    
    # Check consistency/inconsistency lists
    assert "metadata_consistency" in result
    assert "metadata_inconsistency" in result
    assert any("md5sum consistent" in msg for msg in result["metadata_consistency"])
    assert any("read_count inconsistent" in msg for msg in result["metadata_inconsistency"])

def test_patch_file_success(validation_record, requests_mock):
    """Test successful file patching."""
    requests_mock.patch(
        "https://example.com/test-uuid",
        json={"status": "success"}
    )
    
    result = patch_file("https://example.com", ("key", "secret"), validation_record)
    
    # Check that the patch was successful
    assert result["status"] == "success"
    
    # Check that the ETag was included in headers
    assert requests_mock.last_request.headers["If-Match"] == "test-etag"
    
    # Check payload was properly formatted
    payload = json.loads(requests_mock.last_request.text)
    assert "read_count" in payload
    assert "md5sum" in payload
    assert "validated" in payload

def test_patch_file_failure(validation_record, requests_mock):
    """Test handling of patch failure."""
    requests_mock.patch(
        "https://example.com/test-uuid",
        status_code=409,  # Conflict
        json={"status": "error", "detail": "ETag mismatch"}
    )
    
    result = patch_file("https://example.com", ("key", "secret"), validation_record)
    
    # Check that the error is properly returned
    assert "status" in result
    assert result["status"] == "error"
    assert "detail" in result
