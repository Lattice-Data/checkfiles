"""
Unit tests for the upload_report Lambda function.
"""
import os
import json
import base64
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def sample_event():
    """Fixture providing a sample Lambda event."""
    return {
        'instance_id': 'i-1234567890abcdef0',
        'instance_name_suffix': 'test-suffix',
        'instance_id_list': ['i-1234567890abcdef0'],
        'backend_uri': 'https://example.com',
        'query': 'test_query',
        'update': True
    }


@pytest.fixture
def mock_ssm_successful_response():
    """Fixture providing a successful SSM command response with base64 encoded content."""
    sample_content = "Test file content"
    base64_content = base64.b64encode(sample_content.encode()).decode()
    return {
        'Status': 'Success',
        'StandardOutputContent': f"=== Upload Report Debug ===\nSome debug info\n=== File Content ===\n{base64_content}"
    }


@patch.dict(os.environ, {
    'SLACK_TOKEN_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:slack-token',
    'SLACK_CHANNEL_ID_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:channel-id',
    'S3_BUCKET_NAME': 'test-bucket'
})
@patch('boto3.client')
def test_upload_report_success(boto3_client_mock, sample_event, mock_ssm_successful_response):
    """Test successful upload to both Slack and S3."""
    # Import inside test to ensure patched environment
    from main import upload_report_to_slack
    
    # Mock the boto3 clients
    ssm_mock = MagicMock()
    secrets_mock = MagicMock()
    s3_mock = MagicMock()
    
    # Configure boto3 client mock to return our mock clients
    def get_client(service):
        if service == 'ssm':
            return ssm_mock
        elif service == 'secretsmanager':
            return secrets_mock
        elif service == 's3':
            return s3_mock
    
    boto3_client_mock.side_effect = get_client
    
    # Configure the SSM client responses
    send_command_response = {'Command': {'CommandId': 'cmd-123'}}
    ssm_mock.send_command.return_value = send_command_response
    ssm_mock.get_command_invocation.return_value = mock_ssm_successful_response
    
    # Configure the Secrets Manager responses
    secrets_mock.get_secret_value.side_effect = [
        {'SecretString': json.dumps({'BOT_TOKEN': 'xoxb-test-token'})},
        {'SecretString': json.dumps({'CHANNEL_ID': 'C123456'})}
    ]
    
    # Configure S3 client
    s3_mock.put_object.return_value = {}
    
    # Mock the requests module
    with patch('requests.post') as requests_post_mock:
        # Mock Slack API responses
        requests_post_mock.side_effect = [
            # First call - files.getUploadURLExternal
            MagicMock(
                json=lambda: {'ok': True, 'upload_url': 'https://upload.slack.com/test', 'file_id': 'F12345'}
            ),
            # Second call - upload to the URL
            MagicMock(status_code=200),
            # Third call - files.completeUploadExternal
            MagicMock(json=lambda: {'ok': True})
        ]
        
        # Run the function
        result = upload_report_to_slack(sample_event, {})
        
        # Assertions
        assert result['status'] == 'SUCCESS'
        assert 's3_upload_status' in result
        assert result['s3_upload_status'] == 'SUCCESS'
        assert 'slack_upload_status' in result
        assert result['slack_upload_status'] == 'SUCCESS'
        assert 's3_location' in result
        assert 'test-bucket' in result['s3_location']
        
        # Verify mock calls
        ssm_mock.send_command.assert_called_once()
        secrets_mock.get_secret_value.assert_called()
        s3_mock.put_object.assert_called_once()
        assert requests_post_mock.call_count == 3


@patch.dict(os.environ, {
    'SLACK_TOKEN_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:slack-token',
    'SLACK_CHANNEL_ID_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:channel-id',
    'S3_BUCKET_NAME': 'test-bucket'
})
@patch('boto3.client')
def test_upload_report_s3_failure(boto3_client_mock, sample_event, mock_ssm_successful_response):
    """Test handling of S3 upload failure but Slack upload success."""
    # Import inside test to ensure patched environment
    from main import upload_report_to_slack
    
    # Mock the boto3 clients
    ssm_mock = MagicMock()
    secrets_mock = MagicMock()
    s3_mock = MagicMock()
    
    # Configure boto3 client mock
    def get_client(service):
        if service == 'ssm':
            return ssm_mock
        elif service == 'secretsmanager':
            return secrets_mock
        elif service == 's3':
            return s3_mock
    
    boto3_client_mock.side_effect = get_client
    
    # Configure the responses
    ssm_mock.send_command.return_value = {'Command': {'CommandId': 'cmd-123'}}
    ssm_mock.get_command_invocation.return_value = mock_ssm_successful_response
    secrets_mock.get_secret_value.side_effect = [
        {'SecretString': json.dumps({'BOT_TOKEN': 'xoxb-test-token'})},
        {'SecretString': json.dumps({'CHANNEL_ID': 'C123456'})}
    ]
    
    # Configure S3 to fail
    s3_mock.put_object.side_effect = Exception("S3 upload failed")
    
    # Mock requests module
    with patch('requests.post') as requests_post_mock:
        # Mock successful Slack API responses
        requests_post_mock.side_effect = [
            MagicMock(json=lambda: {'ok': True, 'upload_url': 'https://upload.slack.com/test', 'file_id': 'F12345'}),
            MagicMock(status_code=200),
            MagicMock(json=lambda: {'ok': True})
        ]
        
        # Run the function
        result = upload_report_to_slack(sample_event, {})
        
        # Check results
        assert result['status'] == 'SUCCESS'
        assert result['s3_upload_status'] == 'FAILED'
        assert result['slack_upload_status'] == 'SUCCESS' 