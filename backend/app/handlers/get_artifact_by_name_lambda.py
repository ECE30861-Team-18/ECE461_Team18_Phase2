import json
from rds_connection import run_query


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
        # Extract name from path parameters
        path_params = event.get("pathParameters", {})
        name = path_params.get("name")
        
        # Validate name parameter
        if not name:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing artifact name in path"})
            }
        
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
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No such artifact"})
            }
        
        # Deserialize JSON fields if needed
        for artifact in artifacts:
            _deserialize_json_fields(artifact)
        
        # Convert DB rows to ArtifactMetadata per spec
        metadata_list = [
            {
                "name": artifact["name"],
                "id": str(artifact["id"]),
                "type": artifact["type"]
            }
            for artifact in artifacts
        ]
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,GET",
                "Access-Control-Allow-Headers": "Content-Type,X-Authorization"
            },
            "body": json.dumps(metadata_list, default=str)
        }
        
    except Exception as e:
        print(f"Error in get_artifact_by_name_lambda: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
