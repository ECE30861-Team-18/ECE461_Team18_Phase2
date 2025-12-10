"""Tests for tracks_lambda handler"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from unittest.mock import MagicMock

sys.modules['boto3'] = MagicMock()
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()


class TestTracksLambda:
    """Tests for tracks_lambda handler"""
    
    def setup_method(self):
        if 'handlers.tracks_lambda' in sys.modules:
            del sys.modules['handlers.tracks_lambda']
    
    def test_tracks_returns_planned_features(self):
        """Test tracks endpoint returns planned features"""
        from handlers.tracks_lambda import lambda_handler
        
        result = lambda_handler({}, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'plannedTracks' in body or isinstance(body, list)
