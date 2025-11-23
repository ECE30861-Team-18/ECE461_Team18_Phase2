import os
import json
import boto3
import psycopg2
from psycopg2.extras import RealDictCursor
from botocore.exceptions import ClientError

# Global cache so we don’t call Secrets Manager every time
_secret_cache = None
_connection = None


def get_secret():
    """Fetch and cache DB credentials from AWS Secrets Manager."""
    global _secret_cache
    if _secret_cache:
        return _secret_cache

    secret_name = os.environ["SECRET_NAME"]   # From template.yaml
    region_name = os.environ["AWS_REGION"]

    client = boto3.client("secretsmanager", region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        secret_dict = json.loads(response["SecretString"])
    except ClientError as e:
        raise Exception(f"Error retrieving secret {secret_name}: {e}")

    _secret_cache = secret_dict
    return _secret_cache


def get_connection():
    """Return a live PostgreSQL connection (reuse if open)."""
    global _connection
    if _connection and _connection.closed == 0:
        return _connection

    creds = get_secret()

    _connection = psycopg2.connect(
        host=creds["DB_HOST"],
        port=creds.get("DB_PORT", "5432"),
        dbname=creds["DB_NAME"],
        user=creds["DB_USER"],
        password=creds["DB_PASS"],
        connect_timeout=5
    )
    return _connection


def run_query(sql, params=None, fetch=False):
    """
    Execute a SQL query safely using a shared (global) connection.
    Ensures that aborted transactions are rolled back so the connection
    does not get stuck for future Lambda invocations.
    """
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or [])

            if fetch:
                rows = cur.fetchall()
            else:
                rows = None

        conn.commit()
        return rows

    except Exception as e:
        # REQUIRED: Fixes "current transaction is aborted" problem
        conn.rollback()
        raise

