import json
import re
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
    POST /artifact/byRegEx
    Search for artifacts using a regular expression over artifact names and READMEs.
    """
    try:
        # Log the full incoming event for debugging autograder requests
        print(f"[AUTOGRADER DEBUG] Full event: {json.dumps(event)}")
        print(f"[AUTOGRADER DEBUG] Body: {event.get('body', 'EMPTY')}")
        print(f"[AUTOGRADER DEBUG] Headers: {json.dumps(event.get('headers', {}), indent=2)}")
        print(f"[AUTOGRADER DEBUG] HTTP Method: {event.get('httpMethod', 'UNKNOWN')}")
        
        # Parse request body
        body = json.loads(event.get("body", "{}"))
        regex_pattern = body.get("regex")
        print(f"[AUTOGRADER DEBUG] Parsed regex pattern: '{regex_pattern}'")
        
        # Validate regex parameter
        if not regex_pattern:
            response = {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing regex field in request body"})
            }
            print(f"[AUTOGRADER DEBUG] Returning 400 response: {json.dumps(response)}")
            return response
        
        # Validate regex pattern (try to compile it)
        try:
            compiled_regex = re.compile(regex_pattern, re.IGNORECASE | re.DOTALL)
        except re.error as regex_err:
            response = {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": f"Invalid regex pattern: {str(regex_err)}"
                })
            }
            print(f"[AUTOGRADER DEBUG] Returning 400 response: {json.dumps(response)}")
            return response
        
        # Fetch all artifacts with their metadata (including README from metadata)
        sql = """
        SELECT id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at
        FROM artifacts
        ORDER BY created_at DESC;
        """
        
        artifacts = run_query(sql, fetch=True)
        
        if not artifacts:
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No artifact found under this regex"})
            }
            print(f"[AUTOGRADER DEBUG] No artifacts in database, returning 404: {json.dumps(response)}")
            return response
        
        # Deserialize JSON fields
        for artifact in artifacts:
            _deserialize_json_fields(artifact)
        
        # Filter artifacts based on regex match against name and README
        matching_artifacts = []
        
        for artifact in artifacts:
            name = artifact.get("name", "")
            
            # Check if name matches
            if compiled_regex.search(name):
                matching_artifacts.append(artifact)
                continue
            
            # Check if README (from metadata) matches
            metadata = artifact.get("metadata", {})
            if isinstance(metadata, dict):
                readme = metadata.get("readme", "")
                if readme and compiled_regex.search(readme):
                    matching_artifacts.append(artifact)
                    continue
        
        # Return 404 if no matches found
        if not matching_artifacts:
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No artifact found under this regex"})
            }
            print(f"[AUTOGRADER DEBUG] Returning 404 response: {json.dumps(response)}")
            return response
        
        # Convert to ArtifactMetadata per spec
        metadata_list = [
            {
                "name": artifact["name"],
                "id": artifact["id"],
                "type": artifact["type"]
            }
            for artifact in matching_artifacts
        ]
        
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
                "Access-Control-Allow-Headers": "Content-Type,X-Authorization"
            },
            "body": json.dumps(metadata_list, default=str)
        }
        print(f"[AUTOGRADER DEBUG] Returning response with {len(metadata_list)} artifacts")
        return response
        
    except json.JSONDecodeError:
        response = {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }
        print(f"[AUTOGRADER DEBUG] Returning 400 response: {json.dumps(response)}")
        return response
    except Exception as e:
        print(f"Error in get_artifact_by_regex_lambda: {e}")
        response = {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
        print(f"[AUTOGRADER DEBUG] Returning 500 response: {json.dumps(response)}")
        return response
