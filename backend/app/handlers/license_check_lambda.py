import json
import os
import requests
from rds_connection import run_query


def lambda_handler(event, context):
    """
    POST /artifact/model/{id}/license-check
    Assess license compatibility between a model and a GitHub project
    for fine-tuning and inference usage.
    """
    print(f"[LICENSE_CHECK] Incoming event: {json.dumps(event, indent=2)}")
    
    try:
        # Extract artifact ID from path parameters
        path_params = event.get("pathParameters", {})
        artifact_id = path_params.get("id")
        
        if not artifact_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The license check request is malformed or references an unsupported usage context."})
            }
        
        # Parse request body to get github_url
        body = event.get("body", "{}")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "The license check request is malformed or references an unsupported usage context."})
                }
        
        github_url = body.get("github_url")
        if not github_url:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The license check request is malformed or references an unsupported usage context."})
            }
        
        print(f"[LICENSE_CHECK] Checking license compatibility for artifact {artifact_id} with GitHub project: {github_url}")
        
        # Convert to integer for database query
        try:
            artifact_id = int(artifact_id)
        except (ValueError, TypeError):
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The license check request is malformed or references an unsupported usage context."})
            }
        
        # Query artifact to verify it exists and is a model
        sql = """
        SELECT id, type, name, metadata
        FROM artifacts
        WHERE id = %s AND type = 'model';
        """
        
        results = run_query(sql, params=(artifact_id,), fetch=True)
        
        if not results or len(results) == 0:
            print(f"[LICENSE_CHECK] Artifact {artifact_id} not found or not a model")
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The artifact or GitHub project could not be found."})
            }
        
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
        
        # Fetch GitHub project license via API
        github_license = _fetch_github_license(github_url)
        
        if github_license == "not_found":
            print(f"[LICENSE_CHECK] GitHub repository not found")
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "The artifact or GitHub project could not be found."})
            }
        
        if github_license is None:
            print(f"[LICENSE_CHECK] Failed to retrieve GitHub license information")
            return {
                "statusCode": 502,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "External license information could not be retrieved."})
            }
        
        print(f"[LICENSE_CHECK] GitHub project license: {github_license}")
        
        # Assess compatibility
        is_compatible = _check_license_compatibility(model_license, github_license)
        
        print(f"[LICENSE_CHECK] Compatibility result: {is_compatible}")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
                "Access-Control-Allow-Headers": "Content-Type,X-Authorization"
            },
            "body": json.dumps(is_compatible)
        }
        
    except Exception as e:
        print(f"[LICENSE_CHECK] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error", "details": str(e)})
        }


def _fetch_github_license(github_url):
    """
    Fetch license information from a GitHub repository via API.
    Returns:
    - license key (e.g., 'mit', 'apache-2.0') if successful
    - empty string if repo has no license
    - 'not_found' if repository doesn't exist
    - None if API call fails
    """
    try:
        # Parse GitHub URL to extract owner and repo
        parts = github_url.rstrip("/").replace("https://", "").replace("http://", "").split("/")
        
        if len(parts) < 3 or parts[0] != "github.com":
            print(f"[LICENSE_CHECK] Invalid GitHub URL format: {github_url}")
            return "not_found"
        
        owner = parts[1]
        repo = parts[2]
        
        # Remove .git suffix if present
        if repo.endswith(".git"):
            repo = repo[:-4]
        
        print(f"[LICENSE_CHECK] Fetching license for {owner}/{repo}")
        
        # Use GitHub API to fetch license information
        api_url = f"https://api.github.com/repos/{owner}/{repo}/license"
        
        # Get GitHub token from environment
        github_token = os.environ.get("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            print(f"[LICENSE_CHECK] GitHub repository not found or no license file")
            return "not_found"
        
        if response.status_code != 200:
            print(f"[LICENSE_CHECK] GitHub API error: {response.status_code}")
            return None
        
        data = response.json()
        license_info = data.get("license", {})
        license_key = license_info.get("key", "").lower()
        
        print(f"[LICENSE_CHECK] Found GitHub license: {license_key}")
        return license_key if license_key else ""
        
    except requests.exceptions.RequestException as e:
        print(f"[LICENSE_CHECK] Request error fetching GitHub license: {e}")
        return None
    except Exception as e:
        print(f"[LICENSE_CHECK] Error parsing GitHub URL or fetching license: {e}")
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
    
    # If model has no license, assume not compatible
    if not model_license_norm:
        print("[LICENSE_CHECK] Model has no license information, assuming incompatible")
        return False
    
    # If GitHub project has no license, assume not compatible
    if not github_license_norm:
        print("[LICENSE_CHECK] GitHub project has no license, assuming incompatible")
        return False
    
    # Define permissive licenses (generally compatible for fine-tuning and inference)
    permissive_licenses = {
        "mit", "apache-2.0", "apache", "bsd", "bsd-2-clause", "bsd-3-clause",
        "lgpl-2.1", "lgpl", "cc0-1.0", "unlicense", "isc", "cc-by-4.0"
    }
    
    # Define copyleft licenses (require derivative works to be under same license)
    copyleft_licenses = {
        "gpl", "gpl-2.0", "gpl-3.0", "agpl", "agpl-3.0", "cc-by-sa-4.0"
    }
    
    # Define restrictive licenses (not compatible for commercial use)
    restrictive_licenses = {
        "cc-by-nc", "cc-by-nc-sa", "cc-by-nd", "proprietary", "other"
    }
    
    # Check if either is restrictive (e.g., non-commercial)
    model_is_restrictive = any(lic in model_license_norm for lic in restrictive_licenses)
    github_is_restrictive = any(lic in github_license_norm for lic in restrictive_licenses)
    
    if model_is_restrictive or github_is_restrictive:
        print("[LICENSE_CHECK] One or both licenses are restrictive - incompatible")
        return False
    
    # If both are permissive, compatible
    model_is_permissive = any(lic in model_license_norm for lic in permissive_licenses)
    github_is_permissive = any(lic in github_license_norm for lic in permissive_licenses)
    
    if model_is_permissive and github_is_permissive:
        print("[LICENSE_CHECK] Both licenses are permissive - compatible")
        return True
    
    # Check copyleft licenses
    model_is_copyleft = any(lic in model_license_norm for lic in copyleft_licenses)
    github_is_copyleft = any(lic in github_license_norm for lic in copyleft_licenses)
    
    # If model is permissive and GitHub is copyleft, compatible
    # (using the model doesn't create a derivative work of the GitHub code)
    if model_is_permissive and github_is_copyleft:
        print("[LICENSE_CHECK] Model is permissive, GitHub is copyleft - compatible for usage")
        return True
    
    # If model is copyleft and GitHub is permissive, generally compatible
    if model_is_copyleft and github_is_permissive:
        print("[LICENSE_CHECK] Model is copyleft, GitHub is permissive - compatible")
        return True
    
    # If both are copyleft, check if they're the same license
    if model_is_copyleft and github_is_copyleft:
        if model_license_norm == github_license_norm:
            print("[LICENSE_CHECK] Both have same copyleft license - compatible")
            return True
        else:
            print("[LICENSE_CHECK] Different copyleft licenses - incompatible")
            return False
    
    # Default: if we can't determine, assume incompatible for safety
    print(f"[LICENSE_CHECK] Unable to determine compatibility - assuming incompatible")
    return False
