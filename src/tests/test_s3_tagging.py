"""Tests for S3 tagging functionality.

This module contains tests for the S3 tagging functionality provided by the
s3_utils module and its integration with the patching worker.
"""

import unittest
from unittest.mock import patch, MagicMock
import datetime
import sys
import os
import pytest
from typing import Dict, Any, Tuple

# Add parent directory to path to import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils.s3_utils import set_s3_tags

class TestS3Tagging(unittest.TestCase):
    """Test suite for S3 tagging functionality."""
    
    @patch('boto3.client')
    def test_set_s3_tags_success(self, mock_boto3_client: MagicMock) -> None:
        """Test successful S3 tagging.
        
        Args:
            mock_boto3_client: Mock for boto3.client
        """
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
        self.assertEqual(tag_set[1]['Key'], 'validation_version')
        self.assertEqual(tag_set[1]['Value'], '2.0')
        self.assertEqual(tag_set[2]['Key'], 'validation_date')
        
        # Verify result
        self.assertEqual(result['status'], 'success')
    
    @patch('boto3.client')
    def test_set_s3_tags_error(self, mock_boto3_client: MagicMock) -> None:
        """Test error handling in S3 tagging.
        
        Args:
            mock_boto3_client: Mock for boto3.client
        """
        # Setup mock to raise exception
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.put_object_tagging.side_effect = Exception("Test error")
        
        # Call function and verify error handling
        result = set_s3_tags('s3://my-bucket/path/to/file.fastq.gz', True)
        self.assertEqual(result['status'], 'error:Test error')
        
    def test_patching_worker_with_s3_tagging(self) -> None:
        """Test that patching_worker correctly calls set_s3_tags when conditions are met."""
        # First patch the set_s3_tags that patch_worker will use
        with patch('src.worker.patch_worker.set_s3_tags') as mock_set_s3_tags:
            # Set up the mock return value
            mock_set_s3_tags.return_value = {'status': 'success'}
            
            # Now import the module after patching
            from src.worker.patch_worker import patching_worker
            
            # Create a test job
            job = {
                'portal_uri': 'https://www.lattice-data.org/api',
                'auth': ('key', 'secret'),
                'validation_record': MagicMock(validation_success=True, errors=None, uuid='test-uuid', original_etag='etag123'),
                'file_metadata': {'s3_uri': 's3://test-bucket/test-file.fastq.gz', 'uuid': 'test-uuid'},
                'schema_properties': {},
                'update_s3_tags': True,
                'is_lattice_db': True,
                'ignore_active_credentials': True
            }
            
            # Mock all the required dependencies
            with patch('src.worker.patch_worker.check_credentials_expired', return_value=True), \
                 patch('src.worker.patch_worker.fetch_etag_for_uuid', return_value='etag123'), \
                 patch('src.worker.patch_worker.compare_with_db', return_value={'post_json': {'validated': True}}), \
                 patch('src.worker.patch_worker.patch_file', return_value=True):
                
                # Call the function
                result = patching_worker(job)
                
                # Verify S3 tagging was called
                mock_set_s3_tags.assert_called_once_with('s3://test-bucket/test-file.fastq.gz', True)
                
                # Verify result indicates successful tagging
                assert result['s3_tagged'] is True
                
    @patch('boto3.client')
    def test_set_s3_tags_with_validation_failure(self, mock_boto3_client: MagicMock) -> None:
        """Test S3 tagging when validation fails.
        
        Args:
            mock_boto3_client: Mock for boto3.client
        """
        # Setup mock response
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.put_object_tagging.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        # Call function with validation_successful=False
        result = set_s3_tags('s3://my-bucket/path/to/file.fastq.gz', False)
        
        # Verify boto3 was called correctly
        mock_boto3_client.assert_called_once_with('s3')
        mock_s3_client.put_object_tagging.assert_called_once()
        
        # Verify correct bucket and key were used
        call_args = mock_s3_client.put_object_tagging.call_args[1]
        self.assertEqual(call_args['Bucket'], 'my-bucket')
        self.assertEqual(call_args['Key'], 'path/to/file.fastq.gz')
        
        # Verify TagSet includes validation tags with the correct value
        tag_set = call_args['Tagging']['TagSet']
        self.assertEqual(tag_set[0]['Key'], 'validated')
        self.assertEqual(tag_set[0]['Value'], 'false')
        
        # Verify result
        self.assertEqual(result['status'], 'success')