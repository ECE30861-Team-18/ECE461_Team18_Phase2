# backend/app/auth.py
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rds_connection import run_query


def validate_token(headers):
    """
    Validates the X-Authorization header by checking against the database.

    This now performs REAL token validation:
      - Header must exist
      - Token must be non-empty
      - Token should start with "bearer "
      - Token must exist in auth_tokens table and not be expired

    Returns:
        True if token passes validation rules, otherwise False.
    """

    if not headers:
        return False

    # Try both cases for header name (API Gateway may normalize headers)
    token = headers.get("X-Authorization") or headers.get("x-authorization")
    if not token:
        return False

    token = token.strip()
    if len(token) == 0:
        return False

    # Must start with "bearer "
    if not token.lower().startswith("bearer "):
        return False

    jwt_part = token.split(" ", 1)[1]

    # Must look like a JWT: a.b.c
    if len(jwt_part.split(".")) != 3:
        return False

    # Validate token against database
    try:
        sql = """
        SELECT username, expires_at
        FROM auth_tokens
        WHERE token = %s;
        """
        
        results = run_query(sql, params=(jwt_part,), fetch=True)
        
        if not results or len(results) == 0:
            print(f"[AUTH] Token not found in database")
            return False
        
        token_data = results[0]
        expires_at = token_data['expires_at']
        
        # Check if token is expired
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if datetime.utcnow() > expires_at.replace(tzinfo=None):
            print(f"[AUTH] Token expired at {expires_at}")
            return False
        
        print(f"[AUTH] Token validated for user: {token_data['username']}")
        return True
        
    except Exception as e:
        print(f"[AUTH] Token validation error: {e}")
        return False


def require_auth(event):
    """
    Helper for Lambda handlers.
    Returns (is_valid, error_response) so handlers can do:

        valid, error = require_auth(event)
        if not valid:
            return error

    """

    headers = event.get("headers", {})
    if validate_token(headers):
        return True, None

    return False, {
        "statusCode": 403,
        "body": "Authentication failed due to invalid or missing AuthenticationToken.",
        "headers": {"Content-Type": "text/plain"}
    }
