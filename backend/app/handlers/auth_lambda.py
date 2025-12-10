import json
import os
import sys
import jwt
import datetime
import hashlib

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rds_connection import run_query

# Load from env variable or fallback
JWT_SECRET = os.environ.get("JWT_SECRET", "SUPER_SECRET_KEY") 
JWT_ALGO = "HS256"


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except:
        return response(400, {"error": "Invalid JSON"})

    # Extract request fields
    user = body.get("user", {})
    secret = body.get("secret", {})

    username = user.get("name")
    is_admin = user.get("is_admin")
    password = secret.get("password")

    # Validate request structure
    if username is None or is_admin is None or password is None:
        return response(400, {"error": "Malformed request"})

    # -------------------------
    # DATABASE LOOKUP FOR USER
    # -------------------------
    try:
        sql = """
        SELECT username, password_hash, is_admin
        FROM users
        WHERE username = %s;
        """
        
        results = run_query(sql, params=(username,), fetch=True)
        
        if not results or len(results) == 0:
            print(f"[AUTH] User not found: {username}")
            return response(401, {"error": "Invalid credentials"})
        
        user_data = results[0]
        stored_password_hash = user_data['password_hash']
        stored_is_admin = user_data['is_admin']
        
        # Hash the provided password and compare
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if password_hash != stored_password_hash:
            print(f"[AUTH] Invalid password for user: {username}")
            return response(401, {"error": "Invalid credentials"})
        
        # Verify admin status matches if required
        if is_admin and not stored_is_admin:
            print(f"[AUTH] User {username} is not an admin")
            return response(401, {"error": "Invalid credentials"})
        
    except Exception as e:
        print(f"[AUTH] Database error during user lookup: {e}")
        return response(500, {"error": "Internal server error"})

    # -------------------------
    # Generate JWT token
    # -------------------------
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=10)
    payload = {
        "sub": username,
        "admin": stored_is_admin,
        "exp": expiration,
        "iat": datetime.datetime.utcnow()
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

    # -------------------------
    # Store token in database
    # -------------------------
    try:
        insert_sql = """
        INSERT INTO auth_tokens (token, username, expires_at)
        VALUES (%s, %s, %s);
        """
        
        run_query(insert_sql, params=(token, username, expiration), fetch=False)
        print(f"[AUTH] Token stored for user: {username}, expires at: {expiration}")
        
    except Exception as e:
        print(f"[AUTH] Error storing token: {e}")
        # Continue anyway - token is still valid even if storage fails

    resp = response(200, f'bearer {token}')
    
    # Log the authentication event
    log_entry = {
        "timestamp": str(datetime.datetime.utcnow()),
        "requestId": context.aws_request_id,
        "ip": event.get("requestContext", {}).get("identity", {}).get("sourceIp"),
        "httpMethod": event.get("httpMethod"),
        "resourcePath": event.get("resource"),
        "requestBody": event.get("body"),
        "responseBody": resp["body"],
        "status": resp["statusCode"]
    }

    print(json.dumps(log_entry))

    return resp


# Helper to build API Gateway compatible response
def response(code, body_obj):
    return {
        "statusCode": code,
        "body": json.dumps(body_obj)
    }
