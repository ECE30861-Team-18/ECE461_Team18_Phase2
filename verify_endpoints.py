#!/usr/bin/env python3
"""Quick verification of both endpoints with actual data from your registry"""

import requests
import json

API_URL = "https://wc1j5prmsj.execute-api.us-east-1.amazonaws.com/dev"

print("=" * 70)
print("VERIFICATION: Testing both endpoints with real data")
print("=" * 70)

# Test 1: GET /artifact/byName with actual artifact
print("\n1. Testing GET /artifact/byName/google-bert/bert-base-uncased")
print("-" * 70)
response = requests.get(f"{API_URL}/artifact/byName/google-bert/bert-base-uncased")
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"✓ SUCCESS! Found {len(data)} artifact(s)")
    print(json.dumps(data, indent=2))
else:
    print(f"Response: {response.text}")

# Test 2: POST /artifact/byRegEx with simple pattern
print("\n2. Testing POST /artifact/byRegEx with pattern: 'whisper'")
print("-" * 70)
response = requests.post(
    f"{API_URL}/artifact/byRegEx",
    json={"regex": "whisper"},
    headers={"Content-Type": "application/json"}
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"✓ SUCCESS! Found {len(data)} artifact(s) matching 'whisper'")
    print(json.dumps(data, indent=2))
elif response.status_code == 404:
    print("No artifacts found (404)")
else:
    print(f"Response: {response.text}")

# Test 3: POST /artifact/byRegEx with bert pattern
print("\n3. Testing POST /artifact/byRegEx with pattern: 'bert'")
print("-" * 70)
response = requests.post(
    f"{API_URL}/artifact/byRegEx",
    json={"regex": "bert"},
    headers={"Content-Type": "application/json"}
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"✓ SUCCESS! Found {len(data)} artifact(s) matching 'bert'")
    for artifact in data[:5]:  # Show first 5
        print(f"  - {artifact['name']} (ID: {artifact['id']})")
    if len(data) > 5:
        print(f"  ... and {len(data) - 5} more")
else:
    print(f"Response: {response.text}")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
