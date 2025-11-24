#!/usr/bin/env python3
"""
API Test Script for /artifact/byName and /artifact/byRegEx endpoints

This script tests both endpoints by making actual HTTP requests to the deployed API.
You can configure the API endpoint URL and authentication token as needed.

Usage:
    python test_api_endpoints.py
    python test_api_endpoints.py --url https://your-api-url.com/dev
"""

import requests
import json
import argparse
import sys
from typing import Dict, Any


# ANSI color codes for pretty output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a styled header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ {text}{Colors.RESET}")


def test_get_artifact_by_name(base_url: str, auth_token: str = None) -> bool:
    """
    Test GET /artifact/byName/{name} endpoint
    
    Args:
        base_url: Base URL of the API
        auth_token: Optional authentication token
    
    Returns:
        True if tests pass, False otherwise
    """
    print_header("Testing GET /artifact/byName/{name}")
    
    endpoint = f"{base_url}/artifact/byName"
    headers = {
        "Content-Type": "application/json"
    }
    
    if auth_token:
        headers["X-Authorization"] = auth_token
    
    # Test 1: Search for a common artifact name
    test_cases = [
        {
            "name": "bert",
            "description": "Search for artifacts named 'bert'",
            "expected_status": [200, 404]  # 200 if exists, 404 if not found
        },
        {
            "name": "whisper",
            "description": "Search for artifacts named 'whisper'",
            "expected_status": [200, 404]
        },
        {
            "name": "audience-classifier",
            "description": "Search for artifacts named 'audience-classifier'",
            "expected_status": [200, 404]
        }
    ]
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        artifact_name = test_case["name"]
        url = f"{endpoint}/{artifact_name}"
        
        print(f"\nTest {i}: {test_case['description']}")
        print(f"URL: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code in test_case["expected_status"]:
                print_success(f"Request successful (status {response.status_code})")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"Response: {json.dumps(data, indent=2)}")
                        
                        # Validate response structure
                        if isinstance(data, list):
                            print_success(f"Found {len(data)} artifact(s)")
                            for artifact in data:
                                if all(k in artifact for k in ["name", "id", "type"]):
                                    print_success(f"  - {artifact['name']} (ID: {artifact['id']}, Type: {artifact['type']})")
                                else:
                                    print_error(f"  - Invalid artifact structure: {artifact}")
                                    all_passed = False
                        else:
                            print_error("Expected list response")
                            all_passed = False
                    except json.JSONDecodeError as e:
                        print_error(f"Invalid JSON response: {e}")
                        print(f"Response text: {response.text}")
                        all_passed = False
                elif response.status_code == 404:
                    print_info("No artifacts found with this name (expected for empty registry)")
                    try:
                        error_data = response.json()
                        print(f"Response: {json.dumps(error_data, indent=2)}")
                    except:
                        pass
            else:
                print_error(f"Unexpected status code: {response.status_code}")
                print(f"Response: {response.text}")
                all_passed = False
                
        except requests.exceptions.Timeout:
            print_error("Request timed out")
            all_passed = False
        except requests.exceptions.RequestException as e:
            print_error(f"Request failed: {e}")
            all_passed = False
    
    return all_passed


def test_get_artifact_by_regex(base_url: str, auth_token: str = None) -> bool:
    """
    Test POST /artifact/byRegEx endpoint
    
    Args:
        base_url: Base URL of the API
        auth_token: Optional authentication token
    
    Returns:
        True if tests pass, False otherwise
    """
    print_header("Testing POST /artifact/byRegEx")
    
    endpoint = f"{base_url}/artifact/byRegEx"
    headers = {
        "Content-Type": "application/json"
    }
    
    if auth_token:
        headers["X-Authorization"] = auth_token
    
    test_cases = [
        {
            "regex": ".*bert.*",
            "description": "Search for artifacts with 'bert' in name or README",
            "expected_status": [200, 404]
        },
        {
            "regex": ".*?(audience|classifier).*",
            "description": "Search for artifacts with 'audience' or 'classifier'",
            "expected_status": [200, 404]
        },
        {
            "regex": "^whisper.*",
            "description": "Search for artifacts starting with 'whisper'",
            "expected_status": [200, 404]
        },
        {
            "regex": ".*model.*",
            "description": "Search for artifacts with 'model' anywhere",
            "expected_status": [200, 404]
        }
    ]
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"URL: {endpoint}")
        print(f"Regex: {test_case['regex']}")
        
        payload = {"regex": test_case["regex"]}
        
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code in test_case["expected_status"]:
                print_success(f"Request successful (status {response.status_code})")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"Response: {json.dumps(data, indent=2)}")
                        
                        # Validate response structure
                        if isinstance(data, list):
                            print_success(f"Found {len(data)} artifact(s) matching regex")
                            for artifact in data:
                                if all(k in artifact for k in ["name", "id", "type"]):
                                    print_success(f"  - {artifact['name']} (ID: {artifact['id']}, Type: {artifact['type']})")
                                else:
                                    print_error(f"  - Invalid artifact structure: {artifact}")
                                    all_passed = False
                        else:
                            print_error("Expected list response")
                            all_passed = False
                    except json.JSONDecodeError as e:
                        print_error(f"Invalid JSON response: {e}")
                        print(f"Response text: {response.text}")
                        all_passed = False
                elif response.status_code == 404:
                    print_info("No artifacts found matching this regex (expected for empty registry)")
                    try:
                        error_data = response.json()
                        print(f"Response: {json.dumps(error_data, indent=2)}")
                    except:
                        pass
            else:
                print_error(f"Unexpected status code: {response.status_code}")
                print(f"Response: {response.text}")
                all_passed = False
                
        except requests.exceptions.Timeout:
            print_error("Request timed out")
            all_passed = False
        except requests.exceptions.RequestException as e:
            print_error(f"Request failed: {e}")
            all_passed = False
    
    # Test error cases
    print(f"\n{Colors.BOLD}Testing Error Cases:{Colors.RESET}")
    
    # Test 1: Invalid regex
    print("\nTest: Invalid regex pattern")
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"regex": "[invalid(regex"},
            timeout=30
        )
        if response.status_code == 400:
            print_success("Invalid regex properly rejected (400)")
        else:
            print_error(f"Expected 400, got {response.status_code}")
            all_passed = False
    except Exception as e:
        print_error(f"Test failed: {e}")
        all_passed = False
    
    # Test 2: Missing regex field
    print("\nTest: Missing regex field")
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={},
            timeout=30
        )
        if response.status_code == 400:
            print_success("Missing regex field properly rejected (400)")
        else:
            print_error(f"Expected 400, got {response.status_code}")
            all_passed = False
    except Exception as e:
        print_error(f"Test failed: {e}")
        all_passed = False
    
    return all_passed


def main():
    """Main test execution"""
    parser = argparse.ArgumentParser(
        description="Test /artifact/byName and /artifact/byRegEx API endpoints"
    )
    parser.add_argument(
        "--url",
        default="https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev",
        help="Base URL of the API (without trailing slash)"
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Authentication token (X-Authorization header value)"
    )
    
    args = parser.parse_args()
    
    # Remove trailing slash if present
    base_url = args.url.rstrip('/')
    
    print(f"\n{Colors.BOLD}API Endpoint Testing Suite{Colors.RESET}")
    print(f"Target API: {base_url}")
    if args.token:
        print(f"Using authentication token: {args.token[:20]}...")
    else:
        print("No authentication token provided")
    
    # Run tests
    results = []
    
    try:
        results.append(("GET /artifact/byName", test_get_artifact_by_name(base_url, args.token)))
    except Exception as e:
        print_error(f"Failed to test GET /artifact/byName: {e}")
        results.append(("GET /artifact/byName", False))
    
    try:
        results.append(("POST /artifact/byRegEx", test_get_artifact_by_regex(base_url, args.token)))
    except Exception as e:
        print_error(f"Failed to test POST /artifact/byRegEx: {e}")
        results.append(("POST /artifact/byRegEx", False))
    
    # Print summary
    print_header("Test Summary")
    
    for endpoint, passed in results:
        if passed:
            print_success(f"{endpoint}: PASSED")
        else:
            print_error(f"{endpoint}: FAILED")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.RESET}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed!{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
