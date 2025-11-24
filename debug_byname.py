import requests
import json

API_URL = "https://wc1j5prmsj.execute-api.us-east-1.amazonaws.com/dev"

# First, get some actual artifact names from byRegEx
print("Fetching artifact names using byRegEx...")
response = requests.post(f"{API_URL}/artifact/byRegEx", json={"regex": ".*"})

if response.status_code == 200:
    artifacts = response.json()[:10]  # Get first 10
    print(f"\nFound {len(artifacts)} artifacts. Testing byName with their exact names:\n")
    
    for artifact in artifacts:
        exact_name = artifact['name']
        print(f"Testing: '{exact_name}'")
        
        # Try with the exact name from the database
        import urllib.parse
        encoded = urllib.parse.quote(exact_name, safe='')
        r = requests.get(f"{API_URL}/artifact/byName/{encoded}")
        
        if r.status_code == 200:
            print(f"  ✓ SUCCESS - Found via byName!")
            result = r.json()
            print(f"    Returned {len(result)} result(s)")
        elif r.status_code == 404:
            print(f"  ✗ FAILED - 404 Not Found")
        elif r.status_code == 403:
            print(f"  ✗ FAILED - 403 Authentication required")
        else:
            print(f"  ✗ FAILED - Status {r.status_code}: {r.text}")
        print()
else:
    print(f"Failed to fetch artifacts: {response.status_code}")
