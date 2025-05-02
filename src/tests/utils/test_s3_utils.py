"""Tests for S3 tagging functionality."""

import unittest
from unittest.mock import patch, MagicMock
from src.utils.s3_utils import set_s3_tags

class TestS3Tagging(unittest.TestCase):
    """Test suite for S3 tagging functionality."""
    
    @patch('boto3.client')
    def test_set_s3_tags_success(self, mock_boto3_client):
        """Test successful S3 tagging."""
        # Setup mock response
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.put_object_tagging.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        # Call function
        result = set_s3_tags('s3://my-bucket/path/to/file.fastq.gz', True)
        
        # Verify boto3 was called correctly
        mock_boto3_client.assert_called_once_with('s3')
        mock_s3_client.put_object_tagging.assert_called_once()
        
        # Verify correct bucket and key were used
        call_args = mock_s3_client.put_object_tagging.call_args[1]
        self.assertEqual(call_args['Bucket'], 'my-bucket')
        self.assertEqual(call_args['Key'], 'path/to/file.fastq.gz')
        
        # Verify TagSet includes validation tags
        tag_set = call_args['Tagging']['TagSet']
        self.assertEqual(len(tag_set), 3)
        self.assertEqual(tag_set[0]['Key'], 'validated')
        self.assertEqual(tag_set[0]['Value'], 'true')
        
        # Verify result
        self.assertEqual(result['status'], 'success')
    
    @patch('boto3.client')
    def test_set_s3_tags_error(self, mock_boto3_client):
        """Test error handling in S3 tagging."""
        # Setup mock to raise exception
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.put_object_tagging.side_effect = Exception("Test error")
        
        # Call function and verify error handling
        result = set_s3_tags('s3://my-bucket/path/to/file.fastq.gz', True)
        self.assertEqual(result['status'], 'error:Test error')
