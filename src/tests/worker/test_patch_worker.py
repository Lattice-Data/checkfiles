import pytest
from unittest.mock import patch, MagicMock
import datetime

from src.models.validation_record import FileValidationRecord
from src.worker.patch_worker import patching_worker, check_credentials_expired

@pytest.fixture
def validation_record():
    """Create a sample validation record for testing."""
    record = FileValidationRecord("test.fastq", "test-uuid", "test-etag")
    record.validation_success = True
    record.update_info({
        "read_count": 1000,
        "md5sum": "abcdef"
    })
    return record

@pytest.fixture
def job(validation_record):
    """Create a sample job for testing."""
    return {
        'portal_uri': 'https://example.com',
        'auth': ('key', 'secret'),
        'validation_record': validation_record,
        'file_metadata': {
            'uuid': 'test-uuid',
            'read_count': 500
        },
        'schema_properties': {
            'read_count': {'type': 'integer'},
            'validated': {'type': 'boolean'}
        },
        'ignore_active_credentials': True
    }

@patch('src.worker.patch_worker.fetch_etag_for_uuid')
@patch('src.worker.patch_worker.compare_with_db')
@patch('src.worker.patch_worker.patch_file')
def test_patching_worker_success(mock_patch, mock_compare, mock_fetch, job):
    """Test successful patching with the worker."""
    # Configure mocks
    mock_fetch.return_value = 'test-etag'
    mock_compare.return_value = {
        'post_json': {'read_count': 1000, 'validated': True},
        'metadata_consistency': [],
        'metadata_inconsistency': ['read_count inconsistent']
    }
    mock_patch.return_value = {'status': 'success'}
    
    # Run the worker
    result = patching_worker(job)
    
    # Check the result
    assert result == {'status': 'success'}
    
    # Verify the mocks were called correctly
    mock_fetch.assert_called_once_with('https://example.com', 'test-uuid', ('key', 'secret'))
    mock_compare.assert_called_once()
    mock_patch.assert_called_once()

@patch('src.worker.patch_worker.fetch_etag_for_uuid')
def test_patching_worker_etag_mismatch(mock_fetch, job):
    """Test worker handling of ETag mismatch."""
    # Configure the mock to return a different ETag
    mock_fetch.return_value = 'different-etag'
    
    # Run the worker
    result = patching_worker(job)
    
    # Check that patching was skipped
    assert result is None

@patch('src.worker.patch_worker.check_credentials_expired')
def test_patching_worker_credentials_not_expired(mock_check, job):
    """Test worker skipping patch when credentials not expired."""
    # Set ignore_active_credentials to False to test credentials check
    job['ignore_active_credentials'] = False
    
    # Configure the mock to indicate credentials are not expired
    mock_check.return_value = False
    
    # Run the worker
    result = patching_worker(job)
    
    # Check that patching was skipped
    assert result is None
    mock_check.assert_called_once()

@patch('src.worker.patch_worker.requests.get')
def test_check_credentials_expired(mock_get):
    """Test checking if credentials have expired."""
    # Configure the mock for expired credentials
    mock_response = MagicMock()
    mock_response.json.return_value = {
        '@graph': [{
            'upload_credentials': {
                'expiration': '2000-01-01T00:00:00+00:00'  # Expired
            }
        }]
    }
    mock_get.return_value = mock_response
    
    result = check_credentials_expired('https://example.com', 'test-uuid', ('key', 'secret'))
    
    # Should return True for expired credentials
    assert result is True
    
    # Configure the mock for valid credentials
    future_date = (datetime.datetime.now(datetime.timezone.utc) + 
                   datetime.timedelta(days=1)).isoformat()
    mock_response.json.return_value = {
        '@graph': [{
            'upload_credentials': {
                'expiration': future_date  # Not expired
            }
        }]
    }
    
    result = check_credentials_expired('https://example.com', 'test-uuid', ('key', 'secret'))
    
    # Should return False for valid credentials
    assert result is False

def test_patching_worker_success():
    """Test successful patching."""
    # Mock setup
    job = {
        'portal_uri': 'https://test.org/api',
        'auth': ('key', 'secret'),
        'validation_record': MagicMock(validation_success=True, errors=None, uuid='test-uuid', original_etag='etag123'),
        'file_metadata': {'uuid': 'test-uuid'},
        'schema_properties': {},
        'ignore_active_credentials': True
    }
    
    # Mock the dependencies
    with patch('src.worker.patch_worker.check_credentials_expired', return_value=True), \
         patch('src.worker.patch_worker.fetch_etag_for_uuid', return_value='etag123'), \
         patch('src.worker.patch_worker.compare_with_db', return_value={'post_json': {'validated': True}}), \
         patch('src.worker.patch_worker.patch_file', return_value=True):
        
        result = patching_worker(job)
        
        # Check new return format
        assert result['patched'] is True  # Changed from {'status': 'success'}

def test_patching_worker_etag_mismatch():
    """Test etag mismatch handling."""
    # Mock setup
    job = {
        'portal_uri': 'https://test.org/api',
        'auth': ('key', 'secret'),
        'validation_record': MagicMock(validation_success=True, errors=None, uuid='test-uuid', original_etag='etag123'),
        'file_metadata': {'uuid': 'test-uuid'},
        'schema_properties': {},
        'ignore_active_credentials': True
    }
    
    # Mock the dependencies
    with patch('src.worker.patch_worker.check_credentials_expired', return_value=True), \
         patch('src.worker.patch_worker.fetch_etag_for_uuid', return_value='different-etag'):
        
        result = patching_worker(job)
        
        # Check new return format
        assert result['patched'] is False  # Changed from None

def test_patching_worker_credentials_not_expired():
    """Test handling of non-expired credentials."""
    # Mock setup
    job = {
        'portal_uri': 'https://test.org/api',
        'auth': ('key', 'secret'),
        'validation_record': MagicMock(validation_success=True, errors=None, uuid='test-uuid'),
        'file_metadata': {'uuid': 'test-uuid'},
        'schema_properties': {},
    }
    
    # Mock the dependencies
    with patch('src.worker.patch_worker.check_credentials_expired', return_value=False):
        
        result = patching_worker(job)
        
        # Check new return format
        assert result['patched'] is False  # Changed from None
