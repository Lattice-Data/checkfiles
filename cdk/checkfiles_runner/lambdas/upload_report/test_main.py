"""
Unit tests for the upload_report Lambda function.
"""
import os
import json
import base64
import pytest
from unittest.mock import patch, MagicMock, Mock
from moto import mock_s3
import boto3
from main import upload_report_to_slack


@pytest.fixture
def sample_event():
    return {
        'instance_id': 'i-1234567890abcdef0',
        'instance_name_suffix': 'test-suffix-123',
        'instance_id_list': ['i-1234567890abcdef0'],
        'backend_uri': 'https://api.example.com',
        'query': 'type=File&status=pending',
        'update': True
    }


@pytest.fixture
def mock_secrets():
    return {
        'slack_token': json.dumps({'BOT_TOKEN': 'xoxb-test-token'}),
        'slack_channel': json.dumps({'CHANNEL_ID': 'C1234567890'})
    }


@pytest.fixture
def sample_validation_log():
    return """identifier\turi\terrors\tresults\tjson_patch\tLattice patched?\tS3 tag patched?
test_file_1\ts3://bucket/file1.fastq.gz\t{}\t{"file_size": 1000, "read_count": 100}\t{"file_size": 1000, "read_count": 100, "validated": true}\tsuccess\tsuccess
test_file_2\ts3://bucket/file2.fastq.gz\t{}\t{"file_size": 2000, "read_count": 200}\t{"file_size": 2000, "read_count": 200, "validated": true}\tsuccess\tsuccess"""


@mock_s3
@patch.dict('os.environ', {
    'SLACK_TOKEN_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:slack-token',
    'SLACK_CHANNEL_ID_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:slack-channel',
    'S3_BUCKET_NAME': 'test-checkfiles-bucket'
})
@patch('boto3.client')
@patch('requests.post')
def test_upload_report_s3_success(mock_requests_post, boto3_client_mock, sample_event, mock_secrets, sample_validation_log):
    """Test successful upload from S3 to both Slack and S3 reports folder."""
    
    # Set up S3 mock
    s3_resource = boto3.resource('s3', region_name='us-west-1')
    s3_resource.create_bucket(
        Bucket='test-checkfiles-bucket',
        CreateBucketConfiguration={'LocationConstraint': 'us-west-1'}
    )
    
    # Upload test report file to S3
    s3_client = boto3.client('s3', region_name='us-west-1')
    report_key = f"reports/checkfiles-report-{sample_event['instance_name_suffix']}-20240101-120000.tsv"
    s3_client.put_object(
        Bucket='test-checkfiles-bucket',
        Key=report_key,
        Body=sample_validation_log
    )
    
    # Mock AWS clients
    secrets_mock = MagicMock()
    s3_mock = MagicMock()
    
    def mock_client(service_name):
        if service_name == 'secretsmanager':
            return secrets_mock
        elif service_name == 's3':
            return s3_mock
        return MagicMock()
    
    boto3_client_mock.side_effect = mock_client
    
    # Mock secrets manager responses
    secrets_mock.get_secret_value.side_effect = [
        {'SecretString': mock_secrets['slack_token']},
        {'SecretString': mock_secrets['slack_channel']}
    ]
    
    # Mock S3 responses
    s3_mock.list_objects_v2.return_value = {
        'Contents': [{
            'Key': report_key,
            'LastModified': '2024-01-01T12:00:00Z'
        }]
    }
    s3_mock.get_object.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=sample_validation_log.encode('utf-8')))
    }
    
    # Mock Slack API responses
    mock_requests_post.side_effect = [
        # files.getUploadURLExternal response
        Mock(json=lambda: {
            'ok': True, 
            'upload_url': 'https://files.slack.com/upload/test',
            'file_id': 'F1234567890'
        }),
        # File upload response
        Mock(status_code=200),
        # files.completeUploadExternal response
        Mock(json=lambda: {'ok': True})
    ]
    
    # Execute the function
    result = upload_report_to_slack(sample_event, {})
    
    # Verify the result
    assert result['status'] == 'SUCCESS'
    assert 's3_upload_status' in result
    assert result['s3_upload_status'] == 'SUCCESS'
    assert result['slack_upload_status'] == 'SUCCESS'
    assert 'filename' in result
    assert result['filename'].startswith('checkfiles-report-test-suffix-123-')
    assert result['report_s3_key'] == report_key
    
    # Verify S3 operations
    s3_mock.list_objects_v2.assert_called_once()
    s3_mock.get_object.assert_called_once()
    # No put_object call since file is already in permanent location
    # No delete_object call since we keep the file in permanent location
    
    # Verify Slack API calls
    assert mock_requests_post.call_count == 3


@mock_s3
@patch.dict('os.environ', {
    'SLACK_TOKEN_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:slack-token',
    'SLACK_CHANNEL_ID_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:slack-channel',
    'S3_BUCKET_NAME': 'test-checkfiles-bucket'
})
@patch('boto3.client')
def test_upload_report_no_report_file_found(boto3_client_mock, sample_event):
    """Test handling when no report file is found in S3."""
    
    # Mock AWS clients
    secrets_mock = MagicMock()
    s3_mock = MagicMock()
    
    def mock_client(service_name):
        if service_name == 'secretsmanager':
            return secrets_mock
        elif service_name == 's3':
            return s3_mock
        return MagicMock()
    
    boto3_client_mock.side_effect = mock_client
    
    # Mock secrets manager responses
    secrets_mock.get_secret_value.side_effect = [
        {'SecretString': json.dumps({'BOT_TOKEN': 'test-token'})},
        {'SecretString': json.dumps({'CHANNEL_ID': 'test-channel'})}
    ]
    
    # Mock S3 response with no files found
    s3_mock.list_objects_v2.return_value = {}
    
    # Execute the function and expect an exception
    with pytest.raises(Exception) as exc_info:
        upload_report_to_slack(sample_event, {})
    
    assert "No validation report files found in S3" in str(exc_info.value)


@mock_s3
@patch.dict('os.environ', {
    'SLACK_TOKEN_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:slack-token',
    'SLACK_CHANNEL_ID_ARN': 'arn:aws:secretsmanager:us-west-1:123456789012:secret:slack-channel',
    'S3_BUCKET_NAME': 'test-checkfiles-bucket'
})
@patch('boto3.client')
@patch('requests.post')
def test_upload_report_slack_success(mock_requests_post, boto3_client_mock, sample_event, mock_secrets, sample_validation_log):
    """Test successful Slack upload from existing S3 report."""
    
    # Mock AWS clients
    secrets_mock = MagicMock()
    s3_mock = MagicMock()
    
    def mock_client(service_name):
        if service_name == 'secretsmanager':
            return secrets_mock
        elif service_name == 's3':
            return s3_mock
        return MagicMock()
    
    boto3_client_mock.side_effect = mock_client
    
    # Mock secrets manager responses
    secrets_mock.get_secret_value.side_effect = [
        {'SecretString': mock_secrets['slack_token']},
        {'SecretString': mock_secrets['slack_channel']}
    ]
    
    # Mock S3 responses - successful get_object from reports folder
    report_key = f"reports/checkfiles-report-{sample_event['instance_name_suffix']}-20240101-120000.tsv"
    s3_mock.list_objects_v2.return_value = {
        'Contents': [{
            'Key': report_key,
            'LastModified': '2024-01-01T12:00:00Z'
        }]
    }
    s3_mock.get_object.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=sample_validation_log.encode('utf-8')))
    }
    
    # Mock successful Slack API responses
    mock_requests_post.side_effect = [
        Mock(json=lambda: {
            'ok': True, 
            'upload_url': 'https://files.slack.com/upload/test',
            'file_id': 'F1234567890'
        }),
        Mock(status_code=200),
        Mock(json=lambda: {'ok': True})
    ]
    
    # Execute the function
    result = upload_report_to_slack(sample_event, {})
    
    # Verify the result
    assert result['status'] == 'SUCCESS'
    assert result['s3_upload_status'] == 'SUCCESS'  # File already in S3 from run_checkfiles
    assert result['slack_upload_status'] == 'SUCCESS' 