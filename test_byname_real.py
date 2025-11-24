import requests
import json
import urllib.parse

API_URL = "https://wc1j5prmsj.execute-api.us-east-1.amazonaws.com/dev"

# Test with actual artifact names from your registry
test_artifacts = [
    "openai/whisper",
    "google-bert/bert-base-uncased", 
    "vikhyatk/moondream2",
    "parvk11/audience_classifier_model"
]

print("="*70)
print("TESTING: GET /artifact/byName/{name} with REAL artifacts")
print("="*70)

for artifact_name in test_artifacts:
    # URL encode the name (important for names with slashes)
    encoded_name = urllib.parse.quote(artifact_name, safe='')
    url = f"{API_URL}/artifact/byName/{encoded_name}"
    
    print(f"\n{'='*70}")
    print(f"Artifact: {artifact_name}")
    print(f"URL: {url}")
    
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ SUCCESS! Found {len(data)} artifact(s)")
        for artifact in data:
            print(f"  Name: {artifact['name']}")
            print(f"  ID: {artifact['id']}")
            print(f"  Type: {artifact['type']}")
    elif response.status_code == 404:
        print(f"✗ Not found (404)")
        print(f"  Response: {response.text}")
    elif response.status_code == 403:
        print(f"✗ Authentication required (403)")
        print(f"  Response: {response.text}")
    else:
        print(f"✗ Error {response.status_code}")
        print(f"  Response: {response.text}")

print(f"\n{'='*70}")
print("TEST COMPLETE")
print("="*70)
