"""Tests for delete_artifact_lambda handler"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from unittest.mock import patch, MagicMock

sys.modules['boto3'] = MagicMock()
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()


class TestDeleteArtifactLambda:
    """Tests for delete_artifact_lambda handler"""
    
    def setup_method(self):
        if 'handlers.delete_artifact_lambda' in sys.modules:
            del sys.modules['handlers.delete_artifact_lambda']
    
    @patch('handlers.delete_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    @patch('boto3.client')
    def test_delete_artifact_success(self, mock_boto_client, mock_run_query, mock_require_auth):
        """Test successful artifact deletion"""
        from handlers.delete_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        mock_run_query.side_effect = [
            [{'id': 1, 'download_url': 's3://bucket/model/1/'}],
            None
        ]
        
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'artifact_type': 'model', 'id': '1'}
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
    
    @patch('handlers.delete_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_delete_artifact_not_found(self, mock_run_query, mock_require_auth):
        """Test deleting non-existent artifact"""
        from handlers.delete_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        mock_run_query.return_value = []
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'artifact_type': 'model', 'id': '999'}
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 404
