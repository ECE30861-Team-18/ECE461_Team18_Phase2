import json
import re

# Simulated artifacts data (shared across handlers in a real application, this would be a database)
FAKE_ARTIFACTS = [
    {
        "name": "bert-base-cased",
        "id": "bert-001",
        "type": "model"
    },
    {
        "name": "gpt2-small",
        "id": "gpt2-002",
        "type": "model"
    },
    {
        "name": "falcon-7b-instruct",
        "id": "falcon-003",
        "type": "model"
    },
    {
        "name": "bookcorpus",
        "id": "book-004",
        "type": "dataset"
    },
    {
        "name": "google-research-bert",
        "id": "code-005",
        "type": "code"
    },
    {
        "name": "audience-classifier",
        "id": "aud-006",
        "type": "model"
    },
    {
        "name": "openai-whisper",
        "id": "whisper-007",
        "type": "code"
    }
]


def lambda_handler(event, context):
    """
    Lambda function to search artifacts by regex pattern.
    Endpoint: POST /artifact/byRegEx
    
    Expected request body:
    {
        "regex": "<regular_expression>"
    }
    
    Returns a list of ArtifactMetadata matching the regex pattern.
    """
    
    # Standard CORS headers
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Access-Control-Allow-Headers": "Content-Type,X-Authorization",
        "Content-Type": "application/json"
    }
    
    # Log the raw event to CloudWatch
    print(json.dumps(event, indent=2))
    
    # Handle OPTIONS preflight request
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": ""
        }
    
    # Check for X-Authorization header (authentication)
    auth_header = None
    if event.get("headers"):
        # Headers may be case-insensitive, check both cases
        auth_header = event["headers"].get("X-Authorization") or event["headers"].get("x-authorization")
    
    if not auth_header:
        return {
            "statusCode": 403,
            "headers": headers,
            "body": json.dumps({"error": "Authentication failed due to invalid or missing AuthenticationToken."})
        }
    
    # Parse request body
    try:
        body = event.get("body")
        if body is None:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid"})
            }
        
        # Handle string body (API Gateway may pass body as string)
        if isinstance(body, str):
            body = json.loads(body)
        
        regex_pattern = body.get("regex")
        
        if regex_pattern is None or not isinstance(regex_pattern, str):
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid"})
            }
        
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({"error": "There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid"})
        }
    
    # Validate and compile regex pattern
    try:
        pattern = re.compile(regex_pattern)
    except re.error:
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({"error": "There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid"})
        }
    
    # Search for artifacts matching the regex pattern
    matching_artifacts = []
    for artifact in FAKE_ARTIFACTS:
        # Search in artifact name
        if pattern.search(artifact["name"]):
            matching_artifacts.append({
                "name": artifact["name"],
                "id": artifact["id"],
                "type": artifact["type"]
            })
    
    # Return 404 if no artifacts found
    if not matching_artifacts:
        return {
            "statusCode": 404,
            "headers": headers,
            "body": json.dumps({"error": "No artifact found under this regex."})
        }
    
    # Return the matching artifacts
    return {
        "statusCode": 200,
        "headers": headers,
        "body": json.dumps(matching_artifacts)
    }
