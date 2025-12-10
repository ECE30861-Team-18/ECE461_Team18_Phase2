import json
import os
from rds_connection import run_query
from url_handler import URLHandler
from data_retrieval import GitHubAPIClient
from auth import require_auth
import traceback  # <<< LOGGING


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
    """
    POST /artifact/model/{id}/license-check
    Assess license compatibility between a model and a GitHub project
    for fine-tuning and inference usage.
    """

    log_event(event, context)  # <<< LOGGING

    print(f"[LICENSE_CHECK] Incoming event: {json.dumps(event, indent=2)}")
    
    try:
        # Validate authentication
        valid, error_response = require_auth(event)
        if not valid:
            return error_response
        
        # Extract artifact ID from path parameters
        path_params = event.get("pathParameters", {})
        artifact_id = path_params.get("id")
        
        if not artifact_id:
            response = {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The license check request is malformed or references an unsupported usage context."})
            }
            log_response(response)  # <<< LOGGING
            return response
        
        # Parse request body to get github_url
        body = event.get("body", "{}")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                response = {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "The license check request is malformed or references an unsupported usage context."})
                }
                log_response(response)  # <<< LOGGING
                return response
        
        github_url = body.get("github_url")
        if not github_url:
            response = {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The license check request is malformed or references an unsupported usage context."})
            }
            log_response(response)  # <<< LOGGING
            return response
        
        print(f"[LICENSE_CHECK] Checking license compatibility for artifact {artifact_id} with GitHub project: {github_url}")
        
        # Convert to integer for database query
        try:
            artifact_id = int(artifact_id)
        except (ValueError, TypeError):
            print(f"[LICENSE_CHECK] Invalid artifact ID format: {artifact_id}")
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The artifact or GitHub project could not be found."})
            }
            log_response(response)  # <<< LOGGING
            return response
        
        # Query artifact to verify it exists and is a model
        sql = """
        SELECT id, type, name, metadata
        FROM artifacts
        WHERE id = %s AND type = 'model';
        """
        
        results = run_query(sql, params=(artifact_id,), fetch=True)
        
        if not results or len(results) == 0:
            print(f"[LICENSE_CHECK] Artifact {artifact_id} not found or not a model")
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The artifact or GitHub project could not be found."})
            }
            log_response(response)  # <<< LOGGING
            return response
        
        artifact = results[0]
        metadata = artifact.get("metadata", {})
        
        # Parse metadata JSON if it's a string
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        
        # Extract model license from metadata
        model_license = metadata.get("license", "").lower() if metadata.get("license") else ""
        
        print(f"[LICENSE_CHECK] Model license: {model_license}")
        
        # Parse and fetch GitHub project license using existing tools
        github_license = _fetch_github_license(github_url)
        
        if github_license == "not_found":
            print(f"[LICENSE_CHECK] GitHub repository not found")
            response = {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The artifact or GitHub project could not be found."})
            }
            log_response(response)  # <<< LOGGING
            return response
        
        if github_license is None:
            print(f"[LICENSE_CHECK] Failed to retrieve GitHub license information")
            response = {
                "statusCode": 502,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "External license information could not be retrieved."})
            }
            log_response(response)  # <<< LOGGING
            return response
        
        print(f"[LICENSE_CHECK] GitHub project license: {github_license}")
        
        # Assess compatibility
        is_compatible = _check_license_compatibility(model_license, github_license)
        
        print(f"[LICENSE_CHECK] Compatibility result: {is_compatible}")
        
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
                "Access-Control-Allow-Headers": "Content-Type,X-Authorization"
            },
            "body": json.dumps(is_compatible)
        }

        log_response(response)  # <<< LOGGING
        return response
        
    except Exception as e:
        print(f"[LICENSE_CHECK] Error: {e}")
        log_exception(e)  # <<< LOGGING

        response = {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error", "details": str(e)})
        }
        log_response(response)  # <<< LOGGING
        return response


def _fetch_github_license(github_url):
    """
    Fetch license information from a GitHub repository using existing GitHubAPIClient.
    Returns:
    - license key (e.g., 'mit', 'apache-2.0') if successful
    - empty string if repo has no license
    - 'not_found' if repository doesn't exist
    - None if API call fails
    """
    try:
        # Use URLHandler to parse the GitHub URL
        url_handler = URLHandler()
        url_data = url_handler.handle_url(github_url)
        
        if not url_data.is_valid or not url_data.owner or not url_data.repository:
            print(f"[LICENSE_CHECK] Invalid GitHub URL format: {github_url}")
            return "not_found"
        
        owner = url_data.owner
        repo = url_data.repository
        
        print(f"[LICENSE_CHECK] Fetching license for {owner}/{repo}")
        
        github_token = os.environ.get("GITHUB_TOKEN")
        github_client = GitHubAPIClient(github_token)
        repo_data = github_client.get_repository_data(owner, repo)
        
        if not repo_data.success:
            print(f"[LICENSE_CHECK] Failed to fetch repository: {repo_data.error_message}")
            if "not found" in repo_data.error_message.lower():
                return "not_found"
            return None
        
        license_key = repo_data.license.lower() if repo_data.license else ""
        
        print(f"[LICENSE_CHECK] Found GitHub license: {license_key}")
        return license_key
        
    except Exception as e:
        print(f"[LICENSE_CHECK] Error fetching GitHub license: {e}")
        return None


def _check_license_compatibility(model_license, github_license):
    """
    Check if the model license is compatible with the GitHub project license
    for fine-tuning and inference usage.
    
    Returns True if compatible, False otherwise.
    """
    # Normalize license strings
    model_license_norm = model_license.strip().lower() if model_license else ""
    github_license_norm = github_license.strip().lower() if github_license else ""
    
    if not model_license_norm:
        print("[LICENSE_CHECK] Model has no license information, assuming incompatible")
        return False
    
    if not github_license_norm:
        print("[LICENSE_CHECK] GitHub project has no license, assuming incompatible")
        return False
    
    permissive_licenses = {
        "mit", "apache-2.0", "apache", "bsd", "bsd-2-clause", "bsd-3-clause",
        "lgpl-2.1", "lgpl", "cc0-1.0", "unlicense", "isc", "cc-by-4.0"
    }
    
    copyleft_licenses = {
        "gpl", "gpl-2.0", "gpl-3.0", "agpl", "agpl-3.0", "cc-by-sa-4.0"
    }
    
    restrictive_licenses = {
        "cc-by-nc", "cc-by-nc-sa", "cc-by-nd", "proprietary", "other"
    }
    
    model_is_restrictive = any(lic in model_license_norm for lic in restrictive_licenses)
    github_is_restrictive = any(lic in github_license_norm for lic in restrictive_licenses)
    
    if model_is_restrictive or github_is_restrictive:
        print("[LICENSE_CHECK] One or both licenses are restrictive - incompatible")
        return False
    
    model_is_permissive = any(lic in model_license_norm for lic in permissive_licenses)
    github_is_permissive = any(lic in github_license_norm for lic in permissive_licenses)
    
    if model_is_permissive and github_is_permissive:
        print("[LICENSE_CHECK] Both licenses are permissive - compatible")
        return True
    
    model_is_copyleft = any(lic in model_license_norm for lic in copyleft_licenses)
    github_is_copyleft = any(lic in github_license_norm for lic in copyleft_licenses)
    
    if model_is_permissive and github_is_copyleft:
        print("[LICENSE_CHECK] Model is permissive, GitHub is copyleft - compatible for usage")
        return True
    
    if model_is_copyleft and github_is_permissive:
        print("[LICENSE_CHECK] Model is copyleft, GitHub is permissive - compatible")
        return True
    
    if model_is_copyleft and github_is_copyleft:
        if model_license_norm == github_license_norm:
            print("[LICENSE_CHECK] Both have same copyleft license - compatible")
            return True
        else:
            print("[LICENSE_CHECK] Different copyleft licenses - incompatible")
            return False
    
    print(f"[LICENSE_CHECK] Unable to determine compatibility - assuming incompatible")
    return False
