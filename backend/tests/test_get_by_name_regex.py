import pytest
import json
import sys
import os

# Add backend/app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from unittest.mock import patch, MagicMock, Mock


# Mock boto3 before importing anything that uses it
sys.modules['boto3'] = MagicMock()
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()


class TestGetArtifactByName:
    """Tests for get_artifact_by_name_lambda handler"""
    
    def setup_method(self):
        """Reset modules before each test"""
        # Force reimport of handlers
        import sys
        if 'handlers.get_artifact_by_name_lambda' in sys.modules:
            del sys.modules['handlers.get_artifact_by_name_lambda']

    @patch('rds_connection.run_query')
    def test_get_by_name_success(self, mock_run_query):
        """Test successful retrieval of artifacts by name"""
        from handlers.get_artifact_by_name_lambda import lambda_handler
        
        # Mock database response
        mock_run_query.return_value = [
            {
                'id': 1,
                'name': 'test-model',
                'type': 'model',
                'source_url': 'https://huggingface.co/test/model',
                'download_url': 's3://bucket/model/1/',
                'net_score': 0.85,
                'ratings': '{"net_score": 0.85}',
                'status': 'available',
                'metadata': '{}',
                'created_at': '2024-01-01'
            },
            {
                'id': 2,
                'name': 'test-model',
                'type': 'model',
                'source_url': 'https://huggingface.co/test/model-v2',
                'download_url': 's3://bucket/model/2/',
                'net_score': 0.90,
                'ratings': '{"net_score": 0.90}',
                'status': 'available',
                'metadata': '{}',
                'created_at': '2024-01-02'
            }
        ]
        
        event = {
            "pathParameters": {"name": "test-model"},
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body) == 2
        assert body[0]['name'] == 'test-model'
        assert body[0]['type'] == 'model'
        assert body[1]['id'] == 2
    
    @patch('rds_connection.run_query')
    def test_get_by_name_not_found(self, mock_run_query):
        """Test retrieval when no artifacts match the name"""
        from handlers.get_artifact_by_name_lambda import lambda_handler
        
        mock_run_query.return_value = []
        
        event = {
            "pathParameters": {"name": "nonexistent"},
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error'] == 'No such artifact'
    
    def test_get_by_name_missing_parameter(self):
        """Test when name parameter is missing"""
        from handlers.get_artifact_by_name_lambda import lambda_handler
        
        event = {
            "pathParameters": {},
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
    
    @patch('rds_connection.run_query')
    def test_get_by_name_database_error(self, mock_run_query):
        """Test handling of database errors"""
        from handlers.get_artifact_by_name_lambda import lambda_handler
        
        mock_run_query.side_effect = Exception("Database connection failed")
        
        event = {
            "pathParameters": {"name": "test-model"},
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body


class TestGetArtifactByRegex:
    """Tests for get_artifact_by_regex_lambda handler"""
    
    def setup_method(self):
        """Reset modules before each test"""
        # Force reimport of handlers
        import sys
        if 'handlers.get_artifact_by_regex_lambda' in sys.modules:
            del sys.modules['handlers.get_artifact_by_regex_lambda']

    @patch('rds_connection.run_query')
    def test_get_by_regex_name_match(self, mock_run_query):
        """Test successful regex match on artifact names"""
        from handlers.get_artifact_by_regex_lambda import lambda_handler
        
        mock_run_query.return_value = [
            {
                'id': 1,
                'name': 'bert-base-uncased',
                'type': 'model',
                'source_url': 'https://huggingface.co/bert/base',
                'download_url': 's3://bucket/model/1/',
                'net_score': 0.85,
                'ratings': '{}',
                'status': 'available',
                'metadata': '{"readme": "BERT model"}',
                'created_at': '2024-01-01'
            },
            {
                'id': 2,
                'name': 'gpt2',
                'type': 'model',
                'source_url': 'https://huggingface.co/gpt2',
                'download_url': 's3://bucket/model/2/',
                'net_score': 0.90,
                'ratings': '{}',
                'status': 'available',
                'metadata': '{"readme": "GPT-2 model"}',
                'created_at': '2024-01-02'
            }
        ]
        
        event = {
            "body": json.dumps({"regex": "bert"}),
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body) == 1
        assert body[0]['name'] == 'bert-base-uncased'
    
    @patch('rds_connection.run_query')
    def test_get_by_regex_readme_match(self, mock_run_query):
        """Test regex match on README content"""
        from handlers.get_artifact_by_regex_lambda import lambda_handler
        
        mock_run_query.return_value = [
            {
                'id': 1,
                'name': 'model-a',
                'type': 'model',
                'source_url': 'https://huggingface.co/test/a',
                'download_url': 's3://bucket/model/1/',
                'net_score': 0.85,
                'ratings': '{}',
                'status': 'available',
                'metadata': '{"readme": "This is a transformer model for NLP tasks"}',
                'created_at': '2024-01-01'
            }
        ]
        
        event = {
            "body": json.dumps({"regex": "transformer"}),
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body) == 1
        assert body[0]['name'] == 'model-a'
    
    @patch('rds_connection.run_query')
    def test_get_by_regex_no_match(self, mock_run_query):
        """Test when regex doesn't match any artifacts"""
        from handlers.get_artifact_by_regex_lambda import lambda_handler
        
        mock_run_query.return_value = [
            {
                'id': 1,
                'name': 'test-model',
                'type': 'model',
                'source_url': 'https://huggingface.co/test/model',
                'download_url': 's3://bucket/model/1/',
                'net_score': 0.85,
                'ratings': '{}',
                'status': 'available',
                'metadata': '{}',
                'created_at': '2024-01-01'
            }
        ]
        
        event = {
            "body": json.dumps({"regex": "nonexistent"}),
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
    
    def test_get_by_regex_invalid_regex(self):
        """Test handling of invalid regex patterns"""
        from handlers.get_artifact_by_regex_lambda import lambda_handler
        
        event = {
            "body": json.dumps({"regex": "[invalid(regex"}),
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'regex' in body['error'].lower()
    
    def test_get_by_regex_missing_parameter(self):
        """Test when regex parameter is missing"""
        from handlers.get_artifact_by_regex_lambda import lambda_handler
        
        event = {
            "body": json.dumps({}),
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
    
    def test_get_by_regex_invalid_json(self):
        """Test handling of invalid JSON in request body"""
        from handlers.get_artifact_by_regex_lambda import lambda_handler
        
        event = {
            "body": "not valid json",
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
    
    @patch('rds_connection.run_query')
    def test_get_by_regex_case_insensitive(self, mock_run_query):
        """Test that regex matching is case-insensitive"""
        from handlers.get_artifact_by_regex_lambda import lambda_handler
        
        mock_run_query.return_value = [
            {
                'id': 1,
                'name': 'BERT-Model',
                'type': 'model',
                'source_url': 'https://huggingface.co/bert/base',
                'download_url': 's3://bucket/model/1/',
                'net_score': 0.85,
                'ratings': '{}',
                'status': 'available',
                'metadata': '{}',
                'created_at': '2024-01-01'
            }
        ]
        
        event = {
            "body": json.dumps({"regex": "bert"}),
            "headers": {"x-authorization": "Bearer token"}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body) == 1
        assert body[0]['name'] == 'BERT-Model'
