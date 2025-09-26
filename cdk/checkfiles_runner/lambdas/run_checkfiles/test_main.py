import json
import pytest
from unittest.mock import patch, MagicMock
from main import run_checkfiles_command, upload_validation_log_to_s3


@pytest.fixture
def sample_event():
    return {
        'instance_id': 'i-1234567890abcdef0',
        'instance_name_suffix': 'test-suffix-123',
        'backend_uri': 'https://api.example.com',
        'query': 'type=File&status=pending',
        'iterator': {'index': 0, 'step': 1, 'count': 144, 'continue': True},
        'update': True,
        'number_of_files_pending': 5
    }


@patch.dict('os.environ', {
    'PORTAL_SECRETS_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:portal-secret'
})
@patch('boto3.client')
@patch('time.sleep')  # Speed up tests
def test_run_checkfiles_command_success(mock_sleep, boto3_client_mock, sample_event):
    """Test successful checkfiles command execution with S3 upload."""
    
    # Mock AWS clients
    ssm_mock = MagicMock()
    s3_mock = MagicMock()
    
    def mock_client(service_name):
        if service_name == 'ssm':
            return ssm_mock
        elif service_name == 's3':
            return s3_mock
        return MagicMock()
    
    boto3_client_mock.side_effect = mock_client
    
    # Mock SSM responses
    ssm_mock.send_command.side_effect = [
        {'Command': {'CommandId': 'cmd-checkfiles-123'}},  # Main checkfiles command
        {'Command': {'CommandId': 'cmd-getlog-123'}}       # Get log command
    ]
    
    ssm_mock.get_command_invocation.side_effect = [
        {  # Main checkfiles command result
            'Status': 'Success',
            'StandardOutputContent': 'Checkfiles completed successfully',
            'StandardErrorContent': ''
        },
        {  # Get log command result
            'Status': 'Success',
            'StandardOutputContent': '''identifier\turi\terrors\tresults\tjson_patch\tLattice patched?\tS3 tag patched?
test_file_1\ts3://bucket/file1.fastq.gz\t{}\t{"file_size": 1000}\t{"file_size": 1000, "validated": true}\tsuccess\tsuccess''',
            'StandardErrorContent': ''
        }
    ]
    
    # Mock S3 put_object
    s3_mock.put_object.return_value = {}
    
    # Execute the function
    with patch('time.strftime', return_value='20240101-120000'):
        result = run_checkfiles_command(sample_event, {})
    
    # Verify the result
    assert result['instance_id'] == sample_event['instance_id']
    assert result['instance_name_suffix'] == sample_event['instance_name_suffix']
    assert result['s3_upload_status'] == 'success'
    assert result['s3_key'] == 'reports/checkfiles-report-test-suffix-123-20240101-120000.tsv'
    
    # Verify SSM calls
    assert ssm_mock.send_command.call_count == 2
    assert ssm_mock.get_command_invocation.call_count == 2
    
    # Verify S3 upload
    s3_mock.put_object.assert_called_once()
    s3_call_args = s3_mock.put_object.call_args[1]
    assert s3_call_args['Bucket'] == 'lattice-checkfiles'
    assert s3_call_args['Key'] == 'reports/checkfiles-report-test-suffix-123-20240101-120000.tsv'
    assert 'identifier\turi\terrors' in s3_call_args['Body'].decode('utf-8')


@patch('boto3.client')
@patch('time.sleep')
def test_upload_validation_log_to_s3_success(mock_sleep, boto3_client_mock):
    """Test successful S3 upload of validation log."""
    
    # Mock AWS clients
    ssm_mock = MagicMock()
    s3_mock = MagicMock()
    
    def mock_client(service_name):
        if service_name == 'ssm':
            return ssm_mock
        elif service_name == 's3':
            return s3_mock
        return MagicMock()
    
    boto3_client_mock.side_effect = mock_client
    
    # Mock SSM response
    ssm_mock.send_command.return_value = {'Command': {'CommandId': 'cmd-123'}}
    ssm_mock.get_command_invocation.return_value = {
        'Status': 'Success',
        'StandardOutputContent': '''identifier\turi\terrors\tresults\tjson_patch\tLattice patched?\tS3 tag patched?
file1\ts3://bucket/file1.fastq.gz\t{}\t{"file_size": 1000}\t{"validated": true}\tsuccess\tsuccess''',
        'StandardErrorContent': ''
    }
    
    # Mock S3 response
    s3_mock.put_object.return_value = {}
    
    # Execute the function
    with patch('time.strftime', return_value='20240101-120000'):
        result = upload_validation_log_to_s3('i-1234567890abcdef0', 'test-suffix')
    
    # Verify the result
    assert result['status'] == 'success'
    assert result['s3_key'] == 'reports/checkfiles-report-test-suffix-20240101-120000.tsv'
    assert result['bucket'] == 'lattice-checkfiles'
    
    # Verify S3 upload
    s3_mock.put_object.assert_called_once()


@patch('boto3.client')
@patch('time.sleep')
def test_upload_validation_log_to_s3_ssm_failure(mock_sleep, boto3_client_mock):
    """Test handling of SSM command failure."""
    
    # Mock AWS clients
    ssm_mock = MagicMock()
    s3_mock = MagicMock()
    
    def mock_client(service_name):
        if service_name == 'ssm':
            return ssm_mock
        elif service_name == 's3':
            return s3_mock
        return MagicMock()
    
    boto3_client_mock.side_effect = mock_client
    
    # Mock SSM failure
    ssm_mock.send_command.return_value = {'Command': {'CommandId': 'cmd-123'}}
    ssm_mock.get_command_invocation.return_value = {
        'Status': 'Failed',
        'StandardOutputContent': '',
        'StandardErrorContent': 'File not found'
    }
    
    # Execute the function
    result = upload_validation_log_to_s3('i-1234567890abcdef0', 'test-suffix')
    
    # Verify the result
    assert result['status'] == 'failed'
    assert 'Failed to retrieve log file' in result['error']
    assert result['s3_key'] is None
    
    # Verify S3 was not called
    s3_mock.put_object.assert_not_called()


@patch('boto3.client')
@patch('time.sleep')
def test_upload_validation_log_to_s3_empty_log(mock_sleep, boto3_client_mock):
    """Test handling of empty log file."""
    
    # Mock AWS clients
    ssm_mock = MagicMock()
    s3_mock = MagicMock()
    
    def mock_client(service_name):
        if service_name == 'ssm':
            return ssm_mock
        elif service_name == 's3':
            return s3_mock
        return MagicMock()
    
    boto3_client_mock.side_effect = mock_client
    
    # Mock SSM response with empty content
    ssm_mock.send_command.return_value = {'Command': {'CommandId': 'cmd-123'}}
    ssm_mock.get_command_invocation.return_value = {
        'Status': 'Success',
        'StandardOutputContent': '',
        'StandardErrorContent': ''
    }
    
    # Execute the function
    result = upload_validation_log_to_s3('i-1234567890abcdef0', 'test-suffix')
    
    # Verify the result
    assert result['status'] == 'failed'
    assert 'Retrieved log file is empty' in result['error']
    assert result['s3_key'] is None 