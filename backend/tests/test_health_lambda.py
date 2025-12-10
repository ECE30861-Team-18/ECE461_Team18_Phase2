"""Tests for health_lambda handler"""
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


class TestHealthLambda:
    """Tests for health_lambda handler"""
    
    def setup_method(self):
        if 'handlers.health_lambda' in sys.modules:
            del sys.modules['handlers.health_lambda']
    
    def test_health_check_success(self):
        """Test successful health check"""
        from handlers.health_lambda import lambda_handler
        
        result = lambda_handler({}, None)
        
        assert result['statusCode'] == 200
        body_str = result['body'] if isinstance(result['body'], str) else json.dumps(result['body'])
        assert 'operational' in body_str.lower() or 'status' in body_str.lower()
    
    def test_health_check_returns_json(self):
        """Test health check returns proper JSON"""
        from handlers.health_lambda import lambda_handler
        
        result = lambda_handler({}, None)
        
        body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
        assert body is not None
