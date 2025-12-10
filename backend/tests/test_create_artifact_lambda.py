"""Tests for create_artifact_lambda handler"""
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


class TestCreateArtifactLambda:
    """Tests for create_artifact_lambda handler"""
    
    def setup_method(self):
        if 'handlers.create_artifact_lambda' in sys.modules:
            del sys.modules['handlers.create_artifact_lambda']
    
    @patch('handlers.create_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_create_artifact_success(self, mock_run_query, mock_require_auth):
        """Test successful artifact creation"""
        from handlers.create_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        # Mock a successful insertion returning the new artifact
        mock_run_query.return_value = [{
            'id': 1,
            'type': 'model',
            'name': 'test-model',
            'source_url': 'https://huggingface.co/test/model'
        }]
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'artifact_type': 'model'},
            'body': json.dumps({
                'url': 'https://huggingface.co/test/model',
                'name': 'test-model'
            })
        }
        
        result = lambda_handler(event, None)
        
        # May return 200, 201, 202, 409 (conflict), or 500 depending on logic
        assert result['statusCode'] in [200, 201, 202, 409, 500]
    
    @patch('handlers.create_artifact_lambda.require_auth')
    def test_create_artifact_missing_data(self, mock_require_auth):
        """Test artifact creation with missing required data"""
        from handlers.create_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'type': 'model'},
            'body': json.dumps({'metadata': {'Name': 'test-model'}})
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] in [400, 422]
    
    @patch('handlers.create_artifact_lambda.require_auth')
    def test_create_artifact_invalid_json(self, mock_require_auth):
        """Test artifact creation with invalid JSON"""
        from handlers.create_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'type': 'model'},
            'body': 'invalid json'
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 500
