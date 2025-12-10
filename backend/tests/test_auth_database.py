import pytest
import sys
import os
import hashlib
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add parent directories to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

app_dir = os.path.join(project_root, 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

handlers_dir = os.path.join(app_dir, 'handlers')
if handlers_dir not in sys.path:
    sys.path.insert(0, handlers_dir)


# ============================================================================
# TEST: auth.py - Token Validation with Database
# ============================================================================

class TestAuthDatabaseValidation:
    """Test database-backed token validation in auth.py"""

    @patch('auth.run_query')
    def test_validate_token_success(self, mock_run_query):
        """Test successful token validation with valid token in database"""
        from auth import validate_token
        
        # Mock database response with valid, non-expired token
        future_time = datetime.utcnow() + timedelta(hours=5)
        mock_run_query.return_value = [{
            'username': 'testuser',
            'expires_at': future_time
        }]
        
        headers = {"X-Authorization": "bearer aaa.bbb.ccc"}
        assert validate_token(headers) is True
        
        # Verify query was called with correct token
        mock_run_query.assert_called_once()
        call_args = mock_run_query.call_args
        assert 'aaa.bbb.ccc' in call_args[1]['params']

    @patch('auth.run_query')
    def test_validate_token_not_in_database(self, mock_run_query):
        """Test token validation fails when token not in database"""
        from auth import validate_token
        
        # Mock empty database response
        mock_run_query.return_value = []
        
        headers = {"X-Authorization": "bearer xyz.abc.def"}
        assert validate_token(headers) is False

    @patch('auth.run_query')
    def test_validate_token_expired(self, mock_run_query):
        """Test token validation fails when token is expired"""
        from auth import validate_token
        
        # Mock database response with expired token
        past_time = datetime.utcnow() - timedelta(hours=1)
        mock_run_query.return_value = [{
            'username': 'testuser',
            'expires_at': past_time
        }]
        
        headers = {"X-Authorization": "bearer aaa.bbb.ccc"}
        assert validate_token(headers) is False

    def test_validate_token_missing_header(self):
        """Test validation fails with missing header"""
        from auth import validate_token
        
        headers = {}
        assert validate_token(headers) is False

    def test_validate_token_empty_header(self):
        """Test validation fails with empty header"""
        from auth import validate_token
        
        headers = {"X-Authorization": ""}
        assert validate_token(headers) is False

    def test_validate_token_wrong_prefix(self):
        """Test validation fails without 'bearer ' prefix"""
        from auth import validate_token
        
        headers = {"X-Authorization": "token aaa.bbb.ccc"}
        assert validate_token(headers) is False

    def test_validate_token_invalid_jwt_format(self):
        """Test validation fails with non-JWT format"""
        from auth import validate_token
        
        headers = {"X-Authorization": "bearer invalidtoken"}
        assert validate_token(headers) is False

    @patch('auth.run_query')
    def test_validate_token_database_error(self, mock_run_query):
        """Test validation fails gracefully on database error"""
        from auth import validate_token
        
        # Mock database error
        mock_run_query.side_effect = Exception("Database connection failed")
        
        headers = {"X-Authorization": "bearer aaa.bbb.ccc"}
        assert validate_token(headers) is False

    @patch('auth.run_query')
    def test_validate_token_case_insensitive_header(self, mock_run_query):
        """Test validation works with lowercase header name"""
        from auth import validate_token
        
        future_time = datetime.utcnow() + timedelta(hours=5)
        mock_run_query.return_value = [{
            'username': 'testuser',
            'expires_at': future_time
        }]
        
        # API Gateway may normalize headers to lowercase
        headers = {"x-authorization": "bearer aaa.bbb.ccc"}
        assert validate_token(headers) is True

    @patch('auth.run_query')
    def test_require_auth_success(self, mock_run_query):
        """Test require_auth returns success for valid token"""
        from auth import require_auth
        
        future_time = datetime.utcnow() + timedelta(hours=5)
        mock_run_query.return_value = [{
            'username': 'testuser',
            'expires_at': future_time
        }]
        
        event = {"headers": {"X-Authorization": "bearer x.y.z"}}
        valid, error = require_auth(event)
        
        assert valid is True
        assert error is None

    @patch('auth.run_query')
    def test_require_auth_failure(self, mock_run_query):
        """Test require_auth returns 403 for invalid token"""
        from auth import require_auth
        
        mock_run_query.return_value = []
        
        event = {"headers": {"X-Authorization": "bearer x.y.z"}}
        valid, error = require_auth(event)
        
        assert valid is False
        assert error is not None
        assert error["statusCode"] == 403
        assert "Authentication failed" in error["body"]


# ============================================================================
# TEST: auth_lambda.py - Authentication Handler with Database
# ============================================================================

class TestAuthLambdaDatabase:
    """Test database-backed authentication in auth_lambda.py"""

    @patch('auth_lambda.run_query')
    @patch('auth_lambda.jwt.encode')
    def test_authentication_success(self, mock_jwt_encode, mock_run_query):
        """Test successful authentication with correct credentials"""
        from auth_lambda import lambda_handler
        
        # Setup
        password = "testpass123"
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Mock database responses
        def mock_query_side_effect(sql, params=None, fetch=False):
            if fetch and "SELECT username" in sql:
                # User lookup
                return [{
                    'username': 'testuser',
                    'password_hash': password_hash,
                    'is_admin': True
                }]
            return None
        
        mock_run_query.side_effect = mock_query_side_effect
        mock_jwt_encode.return_value = "mock.jwt.token"
        
        # Create event
        event = {
            "body": json.dumps({
                "user": {"name": "testuser", "is_admin": True},
                "secret": {"password": password}
            }),
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        # Execute
        response = lambda_handler(event, context)
        
        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "bearer mock.jwt.token" == body

    @patch('auth_lambda.run_query')
    def test_authentication_user_not_found(self, mock_run_query):
        """Test authentication fails for non-existent user"""
        from auth_lambda import lambda_handler
        
        # Mock empty database response
        mock_run_query.return_value = []
        
        event = {
            "body": json.dumps({
                "user": {"name": "nonexistent", "is_admin": False},
                "secret": {"password": "anypass"}
            }),
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert "Invalid credentials" in body["error"]

    @patch('auth_lambda.run_query')
    def test_authentication_wrong_password(self, mock_run_query):
        """Test authentication fails with incorrect password"""
        from auth_lambda import lambda_handler
        
        correct_password = "correctpass"
        password_hash = hashlib.sha256(correct_password.encode()).hexdigest()
        
        mock_run_query.return_value = [{
            'username': 'testuser',
            'password_hash': password_hash,
            'is_admin': False
        }]
        
        event = {
            "body": json.dumps({
                "user": {"name": "testuser", "is_admin": False},
                "secret": {"password": "wrongpass"}
            }),
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 401

    @patch('auth_lambda.run_query')
    def test_authentication_admin_mismatch(self, mock_run_query):
        """Test authentication fails when user is not admin but claims to be"""
        from auth_lambda import lambda_handler
        
        password = "testpass"
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        mock_run_query.return_value = [{
            'username': 'testuser',
            'password_hash': password_hash,
            'is_admin': False  # User is NOT admin
        }]
        
        event = {
            "body": json.dumps({
                "user": {"name": "testuser", "is_admin": True},  # Claiming to be admin
                "secret": {"password": password}
            }),
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 401

    def test_authentication_malformed_request(self):
        """Test authentication fails with malformed request"""
        from auth_lambda import lambda_handler
        
        event = {
            "body": json.dumps({
                "user": {"name": "testuser"}  # Missing is_admin
                # Missing secret entirely
            }),
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 400

    def test_authentication_invalid_json(self):
        """Test authentication fails with invalid JSON"""
        from auth_lambda import lambda_handler
        
        event = {
            "body": "invalid json {{{",
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 400

    @patch('auth_lambda.run_query')
    @patch('auth_lambda.jwt.encode')
    def test_token_stored_in_database(self, mock_jwt_encode, mock_run_query):
        """Test that generated token is stored in auth_tokens table"""
        from auth_lambda import lambda_handler
        
        password = "testpass"
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        def mock_query_side_effect(sql, params=None, fetch=False):
            if fetch:
                return [{
                    'username': 'testuser',
                    'password_hash': password_hash,
                    'is_admin': True
                }]
            return None
        
        mock_run_query.side_effect = mock_query_side_effect
        mock_jwt_encode.return_value = "test.jwt.token"
        
        event = {
            "body": json.dumps({
                "user": {"name": "testuser", "is_admin": True},
                "secret": {"password": password}
            }),
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        response = lambda_handler(event, context)
        
        # Verify token insert was called
        assert mock_run_query.call_count == 2  # One for user lookup, one for token insert
        
        # Check the second call (token insert)
        insert_call = mock_run_query.call_args_list[1]
        assert "INSERT INTO auth_tokens" in insert_call[0][0]
        assert insert_call[1]['params'][0] == "test.jwt.token"
        assert insert_call[1]['params'][1] == "testuser"

    @patch('auth_lambda.run_query')
    def test_sql_injection_prevention_username(self, mock_run_query):
        """Test that SQL injection in username is prevented"""
        from auth_lambda import lambda_handler
        
        mock_run_query.return_value = []
        
        # Attempt SQL injection in username
        malicious_username = "admin'; DROP TABLE users; --"
        
        event = {
            "body": json.dumps({
                "user": {"name": malicious_username, "is_admin": True},
                "secret": {"password": "anypass"}
            }),
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        response = lambda_handler(event, context)
        
        # Should fail authentication (not execute injection)
        assert response["statusCode"] == 401
        
        # Verify parameterized query was used
        mock_run_query.assert_called_once()
        call_args = mock_run_query.call_args
        assert 'params' in call_args[1]
        # The malicious string should be passed as a parameter, not concatenated
        assert malicious_username in call_args[1]['params']

    @patch('auth_lambda.run_query')
    def test_sql_injection_prevention_password(self, mock_run_query):
        """Test that SQL injection attempts in password are safely hashed"""
        from auth_lambda import lambda_handler
        
        password_hash = hashlib.sha256(b"realpass").hexdigest()
        
        mock_run_query.return_value = [{
            'username': 'testuser',
            'password_hash': password_hash,
            'is_admin': False
        }]
        
        # Attempt SQL injection in password
        malicious_password = "pass' OR '1'='1"
        
        event = {
            "body": json.dumps({
                "user": {"name": "testuser", "is_admin": False},
                "secret": {"password": malicious_password}
            }),
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}},
            "httpMethod": "POST",
            "resource": "/authenticate"
        }
        
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        
        response = lambda_handler(event, context)
        
        # Should fail because hashed injection attempt doesn't match stored hash
        assert response["statusCode"] == 401


# ============================================================================
# TEST: Protected Endpoints with Token Validation
# ============================================================================

class TestProtectedEndpoints:
    """Test that all protected endpoints validate tokens"""

    @patch('handlers.list_artifacts_lambda.require_auth')
    @patch('handlers.list_artifacts_lambda.run_query')
    def test_list_artifacts_requires_auth(self, mock_run_query, mock_require_auth):
        """Test that list_artifacts validates authentication"""
        from handlers.list_artifacts_lambda import lambda_handler
        
        # Mock auth failure
        mock_require_auth.return_value = (False, {
            "statusCode": 403,
            "body": "Authentication failed"
        })
        
        event = {
            "headers": {},
            "body": "[]"
        }
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 403
        mock_require_auth.assert_called_once()

    @patch('handlers.delete_artifact_lambda.require_auth')
    def test_delete_artifact_requires_auth(self, mock_require_auth):
        """Test that delete_artifact validates authentication"""
        from handlers.delete_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (False, {
            "statusCode": 403,
            "body": "Authentication failed"
        })
        
        event = {
            "headers": {},
            "pathParameters": {"artifact_type": "model", "id": "123"}
        }
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 403
        mock_require_auth.assert_called_once()

    @patch('handlers.create_artifact_lambda.require_auth')
    def test_create_artifact_requires_auth(self, mock_require_auth):
        """Test that create_artifact validates authentication"""
        from handlers.create_artifact_lambda import lambda_handler
        
        mock_require_auth.return_value = (False, {
            "statusCode": 403,
            "body": "Authentication failed"
        })
        
        event = {
            "headers": {},
            "body": json.dumps({"url": "https://example.com"}),
            "pathParameters": {"artifact_type": "model"}
        }
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        assert response["statusCode"] == 403
        mock_require_auth.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
