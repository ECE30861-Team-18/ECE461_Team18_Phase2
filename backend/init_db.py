import psycopg2
import os
import boto3
import json

# Retrieve database credentials from AWS Secrets Manager
def get_db_credentials():
    secret_name = "DB_CREDS"
    region_name = "us-east-1"
    
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
        return json.loads(secret)
    except Exception as e:
        print(f"Error retrieving secret: {e}")
        raise

# Get credentials
creds = get_db_credentials()

conn = psycopg2.connect(
    host=creds.get("DB_HOST"),
    port=int(creds.get("DB_PORT", 5432)),
    database=creds.get("DB_NAME"),
    user=creds.get("DB_USER"),
    password=creds.get("DB_PASS")
)

cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS artifacts (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT,
    source_url TEXT NOT NULL,
    download_url TEXT,
    net_score FLOAT,
    ratings JSONB,
    status TEXT DEFAULT 'upload_pending',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
""")

# Create artifact_relationships table for lineage tracking
cur.execute("""
CREATE TABLE IF NOT EXISTS artifact_relationships (
    id SERIAL PRIMARY KEY,
    from_artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    to_artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(from_artifact_id, to_artifact_id, relationship_type)
);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_relationships_from ON artifact_relationships(from_artifact_id);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_relationships_to ON artifact_relationships(to_artifact_id);
""")

# Create artifact_dependencies table for dataset/code relationships (separate from lineage)
cur.execute("""
CREATE TABLE IF NOT EXISTS artifact_dependencies (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    model_name TEXT,
    dependency_name TEXT,
    dependency_type TEXT NOT NULL,
    source TEXT DEFAULT 'auto_discovered',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(model_id, artifact_id, dependency_type)
);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_dependencies_model ON artifact_dependencies(model_id);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_dependencies_artifact ON artifact_dependencies(artifact_id);
""")

# Create users table for authentication
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
""")

# Create auth_tokens table for token validation
cur.execute("""
CREATE TABLE IF NOT EXISTS auth_tokens (
    id SERIAL PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_auth_tokens_token ON auth_tokens(token);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_auth_tokens_username ON auth_tokens(username);
""")

# Insert default user with hashed password
# Password: correcthorsebatterystaple123(!__+@**(A'"`;DROP TABLE artifacts;
# Using SHA256 hash
import hashlib
default_password = """correcthorsebatterystaple123(!__+@**(A'"`;DROP TABLE packages;"""
password_hash = hashlib.sha256(default_password.encode()).hexdigest()

cur.execute("""
INSERT INTO users (username, password_hash, is_admin)
VALUES (%s, %s, %s)
ON CONFLICT (username) DO NOTHING;
""", ("ece30861defaultadminuser", password_hash, True))

conn.commit()
cur.close()
conn.close()
print("✅ Tables created successfully!")
print("✅ Default user created: ece30861defaultadminuser")
