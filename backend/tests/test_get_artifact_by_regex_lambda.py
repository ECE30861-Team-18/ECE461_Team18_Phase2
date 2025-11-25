import os
import sys
import json
import pytest

# Add the handlers directory to the path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
handlers_dir = os.path.join(project_root, 'app', 'handlers')
if handlers_dir not in sys.path:
    sys.path.insert(0, handlers_dir)

from app.handlers.get_artifact_by_regex_lambda import lambda_handler


class TestGetArtifactByRegExLambda:
    """Test the byRegEx Lambda handler."""

    def test_successful_regex_search(self):
        """Test successful regex search returning matching artifacts."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": "bert"})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert isinstance(body, list)
        assert len(body) >= 1
        # Check that all results contain "bert" in their name
        for artifact in body:
            assert "bert" in artifact["name"].lower()

    def test_regex_search_with_wildcard(self):
        """Test regex search with wildcard pattern."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": ".*"})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert isinstance(body, list)
        assert len(body) > 0

    def test_regex_search_no_match(self):
        """Test regex search with no matching artifacts."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": "nonexistent_pattern_xyz"})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "error" in body

    def test_missing_auth_header(self):
        """Test request without authentication header."""
        event = {
            "httpMethod": "POST",
            "headers": {},
            "body": json.dumps({"regex": "bert"})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "error" in body

    def test_missing_body(self):
        """Test request without body."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": None
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_missing_regex_field(self):
        """Test request with body but missing regex field."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"other_field": "value"})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_invalid_regex_pattern(self):
        """Test request with invalid regex pattern."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": "[invalid("})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_invalid_json_body(self):
        """Test request with invalid JSON body."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": "not valid json"
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_options_preflight(self):
        """Test OPTIONS preflight request."""
        event = {
            "httpMethod": "OPTIONS",
            "headers": {}
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 200

    def test_lowercase_auth_header(self):
        """Test that lowercase x-authorization header is accepted."""
        event = {
            "httpMethod": "POST",
            "headers": {"x-authorization": "bearer test-token"},
            "body": json.dumps({"regex": "bert"})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 200

    def test_cors_headers_present(self):
        """Test that CORS headers are present in response."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": "bert"})
        }
        
        response = lambda_handler(event, None)
        
        assert "Access-Control-Allow-Origin" in response["headers"]
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_response_contains_required_fields(self):
        """Test that response artifacts contain all required fields."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": "bert"})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        for artifact in body:
            assert "name" in artifact
            assert "id" in artifact
            assert "type" in artifact

    def test_regex_with_special_characters(self):
        """Test regex with special characters."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": "gpt2.*"})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body) >= 1

    def test_regex_case_sensitive(self):
        """Test that regex is case-sensitive by default."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": "BERT"})
        }
        
        response = lambda_handler(event, None)
        
        # BERT (uppercase) should not match bert-base-cased
        assert response["statusCode"] == 404

    def test_regex_non_string_value(self):
        """Test request with non-string regex value."""
        event = {
            "httpMethod": "POST",
            "headers": {"X-Authorization": "bearer test-token"},
            "body": json.dumps({"regex": 123})
        }
        
        response = lambda_handler(event, None)
        
        assert response["statusCode"] == 400
