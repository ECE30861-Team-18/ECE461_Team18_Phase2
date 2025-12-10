"""Tests for get_artifact_lambda handler"""
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


class TestGetArtifactLambda:
    """Tests for get_artifact_lambda handler"""
    
    def setup_method(self):
        if 'handlers.get_artifact_lambda' in sys.modules:
            del sys.modules['handlers.get_artifact_lambda']
    
    @patch('handlers.get_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_get_artifact_success(self, mock_run_query, mock_require_auth):
        """Test successful artifact retrieval"""
        from handlers.get_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        mock_run_query.return_value = [{
            'id': 1,
            'name': 'test-model',
            'type': 'model',
            'version': '1.0.0',
            'source_url': 'https://huggingface.co/test/model',
            'download_url': 's3://bucket/model/1/',
            'net_score': 0.85,
            'metadata': json.dumps({'description': 'Test model'}),
            'ratings': json.dumps({'net_score': 0.85}),
            'status': 'available'
        }]
        
        event = {'pathParameters': {'artifact_type': 'model', 'id': '1'}}
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['metadata']['name'] == 'test-model'
    
    @patch('handlers.get_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_get_artifact_not_found(self, mock_run_query, mock_require_auth):
        """Test retrieving non-existent artifact"""
        from handlers.get_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        mock_run_query.return_value = []
        
        event = {'pathParameters': {'artifact_type': 'model', 'id': '999'}}
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 404
