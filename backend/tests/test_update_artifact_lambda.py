"""Tests for update_artifact_lambda handler"""
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


class TestUpdateArtifactLambda:
    """Tests for update_artifact_lambda handler"""
    
    def setup_method(self):
        if 'handlers.update_artifact_lambda' in sys.modules:
            del sys.modules['handlers.update_artifact_lambda']
    
    @patch('handlers.update_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_update_artifact_success(self, mock_run_query, mock_require_auth):
        """Test successful artifact update"""
        from handlers.update_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        mock_run_query.return_value = [{'id': 1, 'name': 'updated-model', 'type': 'model', 'source_url': 'https://huggingface.co/new/model'}]
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'artifact_type': 'model', 'id': '1'},
            'body': json.dumps({
                'source_url': 'https://huggingface.co/new/model'
            })
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
    
    @patch('handlers.update_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_update_artifact_not_found(self, mock_run_query, mock_require_auth):
        """Test updating non-existent artifact"""
        from handlers.update_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        mock_run_query.return_value = []
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'artifact_type': 'model', 'id': '999'},
            'body': json.dumps({'source_url': 'https://example.com/test'})
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 404
