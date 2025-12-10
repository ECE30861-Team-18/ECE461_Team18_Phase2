"""Tests for rate_artifact_lambda handler"""
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


class TestRateArtifactLambda:
    """Tests for rate_artifact_lambda handler"""
    
    def setup_method(self):
        if 'handlers.rate_artifact_lambda' in sys.modules:
            del sys.modules['handlers.rate_artifact_lambda']
    
    @patch('handlers.rate_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_rate_artifact_success(self, mock_run_query, mock_require_auth):
        """Test successful artifact rating"""
        from handlers.rate_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        
        mock_run_query.return_value = [{
            'id': 1,
            'type': 'model',
            'name': 'test-model',
            'ratings': json.dumps({
                'net_score': 0.85,
                'net_score_latency': 0.1,
                'ramp_up_time': 0.9,
                'ramp_up_time_latency': 0.05,
                'license': 1.0,
                'license_latency': 0.02,
                'bus_factor': 0.7,
                'bus_factor_latency': 0.03,
                'performance_claims': 0.8,
                'performance_claims_latency': 0.1,
                'dataset_and_code_score': 0.75,
                'dataset_and_code_score_latency': 0.12,
                'size_score': {'raspberry_pi': 0.5}
            }),
            'metadata': json.dumps({'category': 'model'})
        }]
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'id': '1'}
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'net_score' in body or 'NetScore' in body
    
    @patch('handlers.rate_artifact_lambda.require_auth')
    @patch('rds_connection.run_query')
    def test_rate_artifact_not_found(self, mock_run_query, mock_require_auth):
        """Test rating non-existent artifact"""
        from handlers.rate_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (True, None)
        mock_run_query.return_value = []
        
        event = {
            'headers': {'X-Authorization': 'bearer valid_token'},
            'pathParameters': {'id': '999'}
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 404
