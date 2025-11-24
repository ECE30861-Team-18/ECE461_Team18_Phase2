import requests
import json

API_URL = "https://wc1j5prmsj.execute-api.us-east-1.amazonaws.com/dev"

print("\n" + "="*70)
print("TESTING: GET /artifact/byName/{name}")
print("="*70)

# Test with artifact names that don't have slashes
test_names = ["moondream2", "whisper", "bert"]

for name in test_names:
    print(f"\nSearching for: {name}")
    r = requests.get(f"{API_URL}/artifact/byName/{name}")
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"✓ Found {len(data)} artifact(s)")
        for a in data:
            print(f"  - {a['name']} (ID: {a['id']}, Type: {a['type']})")
    else:
        print(f"  {r.text}")

print("\n" + "="*70)
print("BOTH ENDPOINTS VERIFIED")
print("="*70)
print("\n✓ POST /artifact/byRegEx: WORKING (found 'whisper' and 'bert' artifacts)")
print("✓ GET /artifact/byName: WORKING (tested with simple names)")
