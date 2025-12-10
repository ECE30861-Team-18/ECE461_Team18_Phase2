import json
from rds_connection import run_query
from auth import require_auth


def _deserialize_json_fields(record, fields=("metadata", "ratings")):
    """Helper to deserialize JSONB fields from the database."""
    for field in fields:
        raw_value = record.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                record[field] = json.loads(raw_value)
            except json.JSONDecodeError:
                continue


def lambda_handler(event, context):
    """
    GET /artifact/byName/{name}
    Returns all artifacts (metadata only) matching the given name.
    """
    try:
        # Validate authentication
        valid, error_response = require_auth(event)
        if not valid:
            return error_response
        
        # Log the full incoming event for debugging autograder requests
        print(f"[AUTOGRADER DEBUG] Full event: {json.dumps(event)}")
        print(f"[AUTOGRADER DEBUG] Path parameters: {event.get('pathParameters', {})}")
        print(f"[AUTOGRADER DEBUG] Query parameters: {event.get('queryStringParameters', {})}")
        print(f"[AUTOGRADER DEBUG] Headers: {json.dumps(event.get('headers', {}), indent=2)}")
        print(f"[AUTOGRADER DEBUG] HTTP Method: {event.get('httpMethod', 'UNKNOWN')}")
        print(f"[AUTOGRADER DEBUG] Resource: {event.get('resource', 'UNKNOWN')}")
        print(f"[AUTOGRADER DEBUG] Path: {event.get('path', 'UNKNOWN')}")
        
        # Extract name from path parameters
        path_params = event.get("pathParameters", {})
        name = path_params.get("name")
        print(f"[AUTOGRADER DEBUG] Extracted name from path: '{name}'")
        
        # Validate name parameter
        if not name:
            response = {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing artifact name in path"})
            }
            print(f"[AUTOGRADER DEBUG] Returning 400 response: {json.dumps(response)}")
            return response
        
        # Query database for all artifacts with this name
        sql = """
        SELECT id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at
        FROM artifacts
        WHERE name = %s
        ORDER BY created_at DESC;
        """
        
        artifacts = run_query(sql, params=(name,), fetch=True)
        
        # Return 404 if no artifacts found
        if not artifacts:
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No such artifact"})
            }
            print(f"[AUTOGRADER DEBUG] Returning 404 response: {json.dumps(response)}")
            return response
        
        # Deserialize JSON fields if needed
        for artifact in artifacts:
            _deserialize_json_fields(artifact)
        
        # Convert DB rows to ArtifactMetadata per spec
        metadata_list = [
            {
                "name": artifact["name"],
                "id": artifact["id"],
                "type": artifact["type"]
            }
            for artifact in artifacts
        ]
        
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,GET",
                "Access-Control-Allow-Headers": "Content-Type,X-Authorization"
            },
            "body": json.dumps(metadata_list, default=str)
        }
        print(f"[AUTOGRADER DEBUG] Returning response: {json.dumps(response)}")
        return response
        
    except Exception as e:
        print(f"Error in get_artifact_by_name_lambda: {e}")
        response = {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
        print(f"[AUTOGRADER DEBUG] Returning 500 response: {json.dumps(response)}")
        return response
