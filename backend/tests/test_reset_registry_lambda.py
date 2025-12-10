"""Tests for reset_registry_lambda handler"""
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


class TestResetRegistryLambda:
    """Tests for reset_registry_lambda handler"""
    
    def setup_method(self):
        if 'handlers.reset_registry_lambda' in sys.modules:
            del sys.modules['handlers.reset_registry_lambda']
    
    @patch('handlers.reset_registry_lambda.s3')
    @patch('handlers.reset_registry_lambda.run_query')
    @patch('handlers.reset_registry_lambda.require_auth')
    def test_reset_registry_success(self, mock_require_auth, mock_run_query, mock_s3):
        """Test successful registry reset - validates auth and endpoint structure"""
        from handlers.reset_registry_lambda import lambda_handler
        
        # Mock successful authentication
        mock_require_auth.return_value = (True, None)
        
        # Mock S3 operations to return empty bucket
        mock_s3.list_objects_v2.return_value = {}  # No objects to delete
        mock_run_query.return_value = None
        
        event = {'headers': {'X-Authorization': 'bearer valid_token'}}
        
        result = lambda_handler(event, None)
        
        # Should return 200 with mocked S3/DB
        assert result['statusCode'] == 200
        assert 'body' in result
        
        # Verify S3 and DB operations were called
        assert mock_s3.list_objects_v2.called
        assert mock_run_query.called
    
    @patch('handlers.reset_registry_lambda.require_auth')
    def test_reset_registry_unauthorized(self, mock_require_auth):
        """Test reset registry without authorization"""
        from handlers.reset_registry_lambda import lambda_handler
        
        mock_require_auth.return_value = (False, {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthorized'})
        })
        
        event = {'headers': {}}
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 401
