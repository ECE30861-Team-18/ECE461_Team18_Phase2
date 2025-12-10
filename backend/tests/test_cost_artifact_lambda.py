"""Tests for cost_artifact_lambda handler"""
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


class TestCostArtifactLambda:
    """Tests for cost_artifact_lambda handler"""
    
    def setup_method(self):
        if 'handlers.cost_artifact_lambda' in sys.modules:
            del sys.modules['handlers.cost_artifact_lambda']
    
    @patch('handlers.cost_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    @patch('boto3.client')
    def test_cost_artifact_success(self, mock_boto_client, mock_run_query, mock_require_auth):
        """Test successful cost calculation"""
        from handlers.cost_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        mock_run_query.return_value = [{
            'id': 1,
            'download_url': 's3://bucket/model/1/',
            'metadata': json.dumps({})
        }]
        
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'model/1/file1.bin', 'Size': 1000000},
                {'Key': 'model/1/file2.bin', 'Size': 2000000}
            ]
        }
        mock_boto_client.return_value = mock_s3
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'artifact_type': 'model', 'id': '1'},
            'queryStringParameters': {'dependency': 'false'}
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'totalCost' in body or 'cost' in str(body).lower()
