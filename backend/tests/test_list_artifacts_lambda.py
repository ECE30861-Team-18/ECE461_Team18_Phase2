"""Tests for list_artifacts_lambda handler"""
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


class TestListArtifactsLambda:
    """Tests for list_artifacts_lambda handler"""
    
    def setup_method(self):
        if 'handlers.list_artifacts_lambda' in sys.modules:
            del sys.modules['handlers.list_artifacts_lambda']
    
    @patch('handlers.list_artifacts_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_list_artifacts_success(self, mock_run_query, mock_require_auth):
        """Test successful artifact listing"""
        from handlers.list_artifacts_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        mock_run_query.return_value = [
            {'id': 1, 'name': 'model1', 'type': 'model', 'version': '1.0.0', 'net_score': 0.85},
            {'id': 2, 'name': 'model2', 'type': 'model', 'version': '2.0.0', 'net_score': 0.90}
        ]
        
        event = {'pathParameters': {'type': 'model'}}
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert isinstance(body, list)
        assert len(body) == 2
    
    @patch('handlers.list_artifacts_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_list_artifacts_empty(self, mock_run_query, mock_require_auth):
        """Test listing artifacts when none exist"""
        from handlers.list_artifacts_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        mock_run_query.return_value = []
        
        event = {'pathParameters': {'type': 'model'}}
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert isinstance(body, list)
        assert len(body) == 0
    
    @patch('handlers.list_artifacts_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_list_artifacts_with_offset(self, mock_run_query, mock_require_auth):
        """Test listing artifacts with pagination offset"""
        from handlers.list_artifacts_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        mock_run_query.return_value = [{'id': 3, 'name': 'model3', 'type': 'model'}]
        
        event = {
            'pathParameters': {'type': 'model'},
            'queryStringParameters': {'offset': '10'}
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
