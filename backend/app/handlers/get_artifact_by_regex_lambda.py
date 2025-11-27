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
# SAFE REGEX VALIDATOR
# -----------------------------
class DangerousRegexError(ValueError):
    """Raised when a potentially dangerous regex pattern is detected."""
    pass


def validate_safe_regex(pattern: str):
    """
    Validate that a regex pattern is safe to execute.
    Raises DangerousRegexError if dangerous patterns are detected.
    Raises re.error if the pattern is invalid.
    """

    DANGEROUS_PATTERNS = [
        r"\(\s*\.\*\s*\)\+",       # (.*)+
        r"\(\s*\.\+\s*\)\+",       # (.+)+
        r"\(\s*\w\+\s*\)\+",       # (a+)+
        r"\(\s*.+\|\s*.+\)\*",     # (a|aa)* or similar ambiguous alternations
        r"\{\s*\d+\s*,\s*100000",  # absurd {m,100000} ranges
        r"\{\s*\d+\s*,\s*\d{5,}",  # any extremely large repetition ranges
    ]

    # Detect and reject catastrophic constructs
    for dp in DANGEROUS_PATTERNS:
        if re.search(dp, pattern):
            raise DangerousRegexError("potentially catastrophic backtracking detected")

    # Try to compile to validate syntax
    return re.compile(pattern, re.IGNORECASE)


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
        # Debug logging
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
            log_response(response)
            return response

        # Validate and compile regex pattern
        try:
            compiled_regex = validate_safe_regex(regex_pattern)
            print(f"[AUTOGRADER DEBUG] Compiled regex with flags: IGNORECASE")
            print(f"[AUTOGRADER DEBUG] Regex pattern: {compiled_regex.pattern}")
            print(f"[AUTOGRADER DEBUG] Regex flags: {compiled_regex.flags}")
        except DangerousRegexError as danger_err:
            response = {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": f"Invalid regex pattern: {str(danger_err)}"
                })
            }
            print(f"[AUTOGRADER DEBUG] Dangerous regex rejected, returning 400")
            log_response(response)
            return response
        except re.error as regex_err:
            response = {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": f"Invalid regex pattern: {str(regex_err)}"
                })
            }
            print(f"[AUTOGRADER DEBUG] Returning 400 response: {json.dumps(response)}")
            log_response(response)
            return response

        # Fetch artifacts
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
            log_response(response)
            return response

        # Deserialize JSON fields
        for artifact in artifacts:
            _deserialize_json_fields(artifact)

        # Filter artifacts
        matching_artifacts = []

        print(f"[AUTOGRADER DEBUG] Filtering {len(artifacts)} artifacts...")

        for idx, artifact in enumerate(artifacts):
            name = artifact.get("name", "")

            # Quick name search
            if compiled_regex.search(name):
                print(f"[AUTOGRADER DEBUG] ✓ MATCH {idx+1}: (name)")
                matching_artifacts.append(artifact)
                continue

            # README search
            metadata = artifact.get("metadata", {})
            if isinstance(metadata, dict):
                readme = metadata.get("readme", "")
                if readme:
                    try:
                        if compiled_regex.search(readme):
                            print(f"[AUTOGRADER DEBUG] ✓ MATCH {idx+1}: (README)")
                            matching_artifacts.append(artifact)
                    except Exception as e:
                        print(f"[AUTOGRADER DEBUG] Regex error on artifact '{name}': {e}")

        print(f"[AUTOGRADER DEBUG] Total matches: {len(matching_artifacts)}")

        # No matches
        if not matching_artifacts:
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No artifact found under this regex"})
            }
            log_response(response)
            return response

        # Convert to API spec
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
        log_response(response)
        return response

    except json.JSONDecodeError:
        response = {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }
        log_response(response)
        return response

    except Exception as e:
        print(f"Error in get_artifact_by_regex_lambda: {e}")
        log_exception(e)

        response = {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
        log_response(response)
        return response
