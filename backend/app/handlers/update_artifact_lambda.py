import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rds_connection import run_query
from auth import require_auth


def _deserialize_json_fields(record, fields=("metadata", "ratings")):
    """Convert JSON strings stored in the DB back into Python objects."""
    for field in fields:
        raw_value = record.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                record[field] = json.loads(raw_value)
            except json.JSONDecodeError:
                continue


def lambda_handler(event, context):
    """Update an artifact's data (e.g., URL) in the database."""

    # Validate authentication
    valid, error_response = require_auth(event)
    if not valid:
        return error_response
    
    print("Incoming event:", json.dumps(event, indent=2))

    # --- Extract path parameters ---
    path_params = event.get("pathParameters") or {}
    artifact_type = path_params.get("artifact_type")
    artifact_id = path_params.get("id")

    if not artifact_type or not artifact_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing artifact_type or id in path"})
        }

    # --- Parse body (new data) ---
    try:
        body = json.loads(event.get("body", "{}"))
        new_url = body.get("source_url")

        if not new_url:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing 'source_url' in request body"})
            }

    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }

    # --- Perform update in the database ---
    try:
        sql = """
        UPDATE artifacts
        SET source_url = %s
        WHERE id = %s AND type = %s
        RETURNING id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at;
        """
        result = run_query(sql, (new_url, artifact_id, artifact_type), fetch=True)

        if not result:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Artifact not found"})
            }

        updated_artifact = result[0]
        _deserialize_json_fields(updated_artifact)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Artifact updated successfully!",
                "artifact": updated_artifact
            }, default=str)
        }

    except Exception as e:
        print("❌ Error updating artifact:", e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
