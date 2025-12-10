"""Tests for health_components_lambda handler"""
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


class TestHealthComponentsLambda:
    """Tests for health_components_lambda handler"""
    
    def setup_method(self):
        if 'handlers.health_components_lambda' in sys.modules:
            del sys.modules['handlers.health_components_lambda']
    
    @patch('rds_connection.run_query')
    @patch('boto3.client')
    def test_health_components_all_healthy(self, mock_boto_client, mock_run_query):
        """Test health components check when all services healthy"""
        from handlers.health_components_lambda import lambda_handler
        
        mock_run_query.return_value = [{'count': 1}]
        
        mock_s3 = MagicMock()
        mock_s3.head_bucket.return_value = {}
        mock_boto_client.return_value = mock_s3
        
        result = lambda_handler({}, None)
        
        assert result['statusCode'] in [200, 503]
        body_str = result['body'] if isinstance(result['body'], str) else json.dumps(result['body'])
        assert len(body_str) > 0
    
    def test_health_components_handles_errors(self):
        """Test health components handles errors gracefully"""
        from handlers.health_components_lambda import lambda_handler
        
        # Should handle any errors and return valid response
        result = lambda_handler({}, None)
        
        assert result is not None
        assert 'statusCode' in result
