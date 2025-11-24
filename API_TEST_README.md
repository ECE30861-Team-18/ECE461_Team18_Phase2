# API Endpoint Testing Guide

This guide explains how to test the `/artifact/byName/{name}` and `/artifact/byRegEx` endpoints using the provided test script.

## Prerequisites

Install the required Python package:

```bash
pip install requests
```

## Quick Start

### 1. Get Your API URL

After deploying your CloudFormation stack, find your API endpoint URL. It should look like:
```
https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev
```

You can find this in:
- The CloudFormation stack outputs (look for `ApiEndpoint`)
- The SAM deployment output
- AWS API Gateway console

### 2. Run the Test Script

**Basic usage (no authentication):**
```bash
python test_api_endpoints.py --url https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev
```

**With authentication token:**
```bash
python test_api_endpoints.py --url https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev --token "bearer YOUR_TOKEN_HERE"
```

## Test Coverage

### GET /artifact/byName/{name}

The script tests:
- ✅ Successful retrieval of artifacts by name
- ✅ Response structure validation (name, id, type fields)
- ✅ Handling of non-existent artifact names (404)
- ✅ Proper JSON formatting

**Test Cases:**
1. Search for "bert"
2. Search for "whisper"
3. Search for "audience-classifier"

### POST /artifact/byRegEx

The script tests:
- ✅ Regex matching on artifact names
- ✅ Regex matching on README content
- ✅ Complex regex patterns with alternation
- ✅ Invalid regex pattern handling (400)
- ✅ Missing regex field handling (400)
- ✅ Response structure validation

**Test Cases:**
1. Pattern: `.*bert.*` (contains "bert")
2. Pattern: `.*?(audience|classifier).*` (contains "audience" OR "classifier")
3. Pattern: `^whisper.*` (starts with "whisper")
4. Pattern: `.*model.*` (contains "model")
5. Invalid pattern: `[invalid(regex` (should return 400)
6. Missing regex field: `{}` (should return 400)

## Expected Output

### Successful Test Run

```
============================================================
Testing GET /artifact/byName/{name}
============================================================

Test 1: Search for artifacts named 'bert'
URL: https://xxx.execute-api.us-east-1.amazonaws.com/dev/artifact/byName/bert
Status Code: 200
✓ Request successful (status 200)
Response: [
  {
    "name": "bert-base-uncased",
    "id": "1234567890",
    "type": "model"
  }
]
✓ Found 1 artifact(s)
✓   - bert-base-uncased (ID: 1234567890, Type: model)

...

============================================================
Test Summary
============================================================

✓ GET /artifact/byName: PASSED
✓ POST /artifact/byRegEx: PASSED

All tests passed!
```

### Empty Registry

If your registry is empty, you'll see 404 responses:

```
Status Code: 404
ℹ No artifacts found with this name (expected for empty registry)
Response: {
  "error": "No such artifact"
}
```

This is expected behavior and the tests will still pass.

## Troubleshooting

### Connection Errors

**Problem:** `Request failed: Connection refused` or similar

**Solution:** 
- Verify your API URL is correct
- Check that the CloudFormation stack deployed successfully
- Ensure you're using the correct stage name (usually `/dev`)

### 403 Forbidden

**Problem:** Authentication failures

**Solution:**
- If the endpoint requires authentication, provide a valid token with `--token`
- Get a token by calling `/authenticate` first (if implemented)

### 500 Internal Server Error

**Problem:** Lambda function errors

**Solution:**
- Check CloudWatch Logs for the Lambda functions
- Verify database connection is working
- Check that all required environment variables are set

### CORS Errors (if testing from browser)

The endpoints should have CORS headers configured. If you see CORS errors:
- Check the `template.yaml` CORS configuration
- Ensure `Access-Control-Allow-Origin` headers are returned

## Manual Testing with curl

You can also test the endpoints manually:

### Test GET /artifact/byName

```bash
curl -X GET "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev/artifact/byName/bert" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

### Test POST /artifact/byRegEx

```bash
curl -X POST "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev/artifact/byRegEx" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -d '{"regex": ".*bert.*"}'
```

## Integration with CI/CD

You can integrate this test script into your CI/CD pipeline:

```bash
# Install dependencies
pip install requests

# Run tests and capture exit code
python test_api_endpoints.py --url $API_URL --token $AUTH_TOKEN

# Exit code 0 = success, 1 = failure
if [ $? -eq 0 ]; then
    echo "API tests passed!"
else
    echo "API tests failed!"
    exit 1
fi
```

## Advanced Usage

### Testing Specific Endpoints Only

Modify the `main()` function in `test_api_endpoints.py` to comment out the tests you don't want to run:

```python
# Run tests
results = []

# Test only byName endpoint
results.append(("GET /artifact/byName", test_get_artifact_by_name(base_url, args.token)))

# Comment out to skip byRegEx tests
# results.append(("POST /artifact/byRegEx", test_get_artifact_by_regex(base_url, args.token)))
```

### Adding Custom Test Cases

Add your own test cases to the `test_cases` lists in each test function:

```python
test_cases = [
    {
        "name": "my-custom-artifact",
        "description": "Search for my custom artifact",
        "expected_status": [200, 404]
    }
]
```

## Next Steps

1. **Deploy your stack** first using SAM CLI
2. **Get the API URL** from the outputs
3. **Run the test script** with your API URL
4. **Check CloudWatch Logs** if any tests fail
5. **Create some test artifacts** in your registry to see 200 responses

For more information, see the main project README.
