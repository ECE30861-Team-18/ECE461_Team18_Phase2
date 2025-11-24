#!/usr/bin/env python3
"""
Quick start script for testing the API endpoints.

Before running, update the API_URL variable with your actual API Gateway URL.
You can find this in the CloudFormation stack outputs or the SAM deployment output.
"""

import subprocess
import sys

# ============================================================================
# CONFIGURATION - UPDATE THIS WITH YOUR ACTUAL API URL
# ============================================================================
API_URL = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev"

# Optional: Add authentication token if needed
AUTH_TOKEN = None  # Set to "bearer YOUR_TOKEN" if required

# ============================================================================

def main():
    """Run the API tests with the configured settings"""
    
    print("=" * 60)
    print("ECE461 Team 18 - API Endpoint Test Runner")
    print("=" * 60)
    print()
    
    # Check if we need to update the URL
    if "YOUR_API_ID" in API_URL:
        print("⚠️  WARNING: Please update the API_URL in this script first!")
        print()
        print("Steps:")
        print("1. Deploy your CloudFormation stack")
        print("2. Get the API URL from the stack outputs")
        print("3. Update the API_URL variable at the top of this script")
        print()
        print("Example URL format:")
        print("  https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev")
        print()
        return 1
    
    # Build command
    cmd = [sys.executable, "test_api_endpoints.py", "--url", API_URL]
    
    if AUTH_TOKEN:
        cmd.extend(["--token", AUTH_TOKEN])
    
    print(f"Running tests against: {API_URL}")
    if AUTH_TOKEN:
        print(f"Using authentication token: {AUTH_TOKEN[:20]}...")
    else:
        print("No authentication token configured")
    print()
    
    # Run the test script
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print("❌ Error: test_api_endpoints.py not found")
        print("Make sure you're running this script from the project root directory")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
