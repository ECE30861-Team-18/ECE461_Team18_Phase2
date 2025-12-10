import requests
import json

# Get the API Gateway URL
api_url = "https://ki39dfhpqc.execute-api.us-east-1.amazonaws.com/dev"

# Test authentication
auth_payload = {
    "user": {
        "name": "ece30861defaultadminuser",
        "is_admin": True
    },
    "secret": {
        "password": """correcthorsebatterystaple123(!__+@**(A'"`;DROP TABLE packages;"""
    }
}

print("Testing /authenticate endpoint...")
print(f"URL: {api_url}/authenticate")
print(f"Payload: {json.dumps(auth_payload, indent=2)}")

response = requests.put(f"{api_url}/authenticate", json=auth_payload)

print(f"\nStatus Code: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"Response Body: {response.text}")

if response.status_code == 200:
    print("\n✅ Authentication successful!")
    token = response.json()
    print(f"Token: {token}")
else:
    print(f"\n❌ Authentication failed!")
    print(f"Error: {response.text}")
