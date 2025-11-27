import json
import re
from rds_connection import run_query
import traceback  # <<< LOGGING


def _deserialize_json_fields(record, fields=("metadata", "ratings")):
    """Helper to deserialize JSONB fields from the database."""
    for field in fields:
        raw_value = record.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                record[field] = json.loads(raw_value)
            except json.JSONDecodeError:
                continue


# -----------------------------
# LOGGING HELPERS
# -----------------------------
def log_event(event, context):  # <<< LOGGING
    print("==== INCOMING EVENT ====")
    try:
        print(json.dumps(event, indent=2))
    except:
        print(event)

    print("==== CONTEXT ====")
    try:
        print(json.dumps({
            "aws_request_id": context.aws_request_id,
            "function_name": context.function_name,
            "memory_limit_in_mb": context.memory_limit_in_mb,
            "function_version": context.function_version
        }, indent=2))
    except:
        pass


def log_response(response):  # <<< LOGGING
    print("==== OUTGOING RESPONSE ====")
    try:
        print(json.dumps(response, indent=2))
    except:
        print(response)


def log_exception(e):  # <<< LOGGING
    print("==== EXCEPTION OCCURRED ====")
    print(str(e))
    traceback.print_exc()


# -----------------------------
# Lambda Handler
# -----------------------------
def lambda_handler(event, context):

    log_event(event, context)  # <<< LOGGING

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
            log_response(response)  # <<< LOGGING
            return response
        
        # Validate regex pattern (try to compile it)
        try:
            # Compile regex with IGNORECASE only (DOTALL not needed and slows down matching)
            compiled_regex = re.compile(regex_pattern, re.IGNORECASE)
            print(f"[AUTOGRADER DEBUG] Compiled regex with flags: IGNORECASE")
            print(f"[AUTOGRADER DEBUG] Regex pattern: {compiled_regex.pattern}")
            print(f"[AUTOGRADER DEBUG] Regex flags: {compiled_regex.flags}")
        except re.error as regex_err:
            response = {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": f"Invalid regex pattern: {str(regex_err)}"
                })
            }
            print(f"[AUTOGRADER DEBUG] Returning 400 response: {json.dumps(response)}")
            log_response(response)  # <<< LOGGING
            return response
        
        # Fetch all artifacts with their metadata
        # Only get essential fields to reduce data transfer and processing time
        sql = """
        SELECT id, type, name, metadata
        FROM artifacts
        ORDER BY created_at DESC;
        """
        
        print(f"[AUTOGRADER DEBUG] Executing query to fetch all artifacts...")
        artifacts = run_query(sql, fetch=True)
        print(f"[AUTOGRADER DEBUG] Query returned {len(artifacts) if artifacts else 0} artifacts")
        
        if not artifacts:
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No artifact found under this regex"})
            }
            print(f"[AUTOGRADER DEBUG] No artifacts in database, returning 404: {json.dumps(response)}")
            log_response(response)  # <<< LOGGING
            return response
        
        # Deserialize JSON fields
        for artifact in artifacts:
            _deserialize_json_fields(artifact)
        
        # Filter artifacts
        matching_artifacts = []
        
        print(f"[AUTOGRADER DEBUG] Starting to filter {len(artifacts)} artifacts against pattern '{regex_pattern}'")
        
        for idx, artifact in enumerate(artifacts):
            name = artifact.get("name", "")
            
            # Quick check: name matching (fast)
            if compiled_regex.search(name):
                print(f"[AUTOGRADER DEBUG] ✓ MATCH {idx+1}: name='{name}' (matched on name)")
                matching_artifacts.append(artifact)
                continue
            
            # README matching (only if name didn't match)
            metadata = artifact.get("metadata", {})
            if isinstance(metadata, dict):
                readme = metadata.get("readme", "")
                if readme:
                    try:
                        # Search full README
                        if compiled_regex.search(readme):
                            print(f"[AUTOGRADER DEBUG] ✓ MATCH {idx+1}: name='{name}' (matched in README)")
                            matching_artifacts.append(artifact)
                    except Exception as e:
                        # Catch catastrophic backtracking or other regex issues
                        print(f"[AUTOGRADER DEBUG] Regex error on '{name}': {e}")
        
        print(f"[AUTOGRADER DEBUG] Total matches found: {len(matching_artifacts)}")
        
        # Return 404 if no matches found
        if not matching_artifacts:
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No artifact found under this regex"})
            }
            print(f"[AUTOGRADER DEBUG] Returning 404 response: {json.dumps(response)}")
            log_response(response)  # <<< LOGGING
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
        log_response(response)  # <<< LOGGING
        return response
        
    except json.JSONDecodeError:
        response = {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }
        print(f"[AUTOGRADER DEBUG] Returning 400 response: {json.dumps(response)}")
        log_response(response)  # <<< LOGGING
        return response

    except Exception as e:
        print(f"Error in get_artifact_by_regex_lambda: {e}")
        log_exception(e)  # <<< LOGGING

        response = {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
        print(f"[AUTOGRADER DEBUG] Returning 500 response: {json.dumps(response)}")
        log_response(response)  # <<< LOGGING
        return response
