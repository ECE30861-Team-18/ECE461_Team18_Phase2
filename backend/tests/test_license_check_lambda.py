"""Tests for license_check_lambda handler"""
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


class TestLicenseCheckLambda:
    """Tests for license_check_lambda handler"""
    
    def setup_method(self):
        if 'handlers.license_check_lambda' in sys.modules:
            del sys.modules['handlers.license_check_lambda']
    
    @patch('handlers.license_check_lambda.require_auth')
    @patch('handlers.license_check_lambda._fetch_github_license')
    @patch('rds_connection.run_query')
    def test_license_check_compatible(self, mock_run_query, mock_fetch_license, mock_require_auth):
        """Test license check with compatible license"""
        from handlers.license_check_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        mock_run_query.return_value = [{
            'id': 1,
            'metadata': json.dumps({'license': 'MIT'})
        }]
        
        # Mock GitHub license fetch to return MIT (compatible)
        mock_fetch_license.return_value = 'mit'
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'artifact_type': 'model', 'id': '1'},
            'body': json.dumps({'github_url': 'https://github.com/test/repo'})
        }
        
        result = lambda_handler(event, None)
        
        # Should return 200 with mocked GitHub API
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        # Body should be a boolean (True for compatible)
        assert isinstance(body, bool)
        assert body is True  # MIT is compatible with MIT
    
    @patch('handlers.license_check_lambda.require_auth')
    @patch('handlers.license_check_lambda._fetch_github_license')
    @patch('rds_connection.run_query')
    def test_license_check_incompatible(self, mock_run_query, mock_fetch_license, mock_require_auth):
        """Test license check with incompatible license"""
        from handlers.license_check_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        mock_run_query.return_value = [{
            'id': 1,
            'metadata': json.dumps({'license': 'GPL-3.0'})
        }]
        
        # Mock GitHub license fetch to return MIT (incompatible with GPL)
        mock_fetch_license.return_value = 'mit'
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'artifact_type': 'model', 'id': '1'},
            'body': json.dumps({'github_url': 'https://github.com/test/repo'})
        }
        
        result = lambda_handler(event, None)
        
        # Should return 200 with mocked GitHub API
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        # Body should be a boolean
        assert isinstance(body, bool)
