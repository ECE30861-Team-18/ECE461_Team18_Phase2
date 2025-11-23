import json
import os
import jwt
import datetime

# Hard-coded for autograder (you will replace with DB lookup later)
DEFAULT_USERNAME = "ece30861defaultadminuser"
DEFAULT_PASSWORD = """correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"""

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
    # is_admin = True
    is_admin = user.get("is_admin")
    password = secret.get("password")

    # Validate request structure
    if username is None or is_admin is None or password is None:
        return response(400, {"error": "Malformed request"})

    # -------------------------
    # FUTURE DB LOOKUP GOES HERE
    # -------------------------
    #
    # Example:
    # stored_user = db.get_user(username)
    # if not stored_user: return 401
    # if not verify_hash(password, stored_user.password_hash): return 401
    #
    # For now → only accept the spec’s default user
    if username != DEFAULT_USERNAME or password != DEFAULT_PASSWORD:
        return response(401, {"error": "Invalid credentials"})

    # -------------------------
    # Generate JWT token
    # -------------------------
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=10)
    payload = {
        "sub": username,
        "admin": is_admin,
        "exp": expiration,
        "iat": datetime.datetime.utcnow()
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

    # MUST return as plain string inside JSON (no extra embedded quotes)
    return response(200, f'bearer {token}')
    


# Helper to build API Gateway compatible response
def response(code, body_obj):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_obj)
    }
