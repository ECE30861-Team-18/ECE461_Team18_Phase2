# Get By Name and Get By Regex Implementation

## Overview
This document describes the implementation of two NON-BASELINE API endpoints for searching artifacts:
1. **GET /artifact/byName/{name}** - Search by exact artifact name
2. **POST /artifact/byRegEx** - Search using regular expressions

## Implementation Files

### Lambda Handlers
1. **`backend/app/handlers/get_artifact_by_name_lambda.py`**
   - Handles GET requests to `/artifact/byName/{name}`
   - Returns all artifacts matching the exact name
   - Returns 404 if no matches found

2. **`backend/app/handlers/get_artifact_by_regex_lambda.py`**
   - Handles POST requests to `/artifact/byRegEx`
   - Supports regex matching on both artifact names and README content
   - Case-insensitive matching using `re.IGNORECASE`
   - Returns 400 for invalid regex patterns

### AWS Configuration
- **`template.yaml`** updated with:
  - Two new Lambda function definitions
  - API Gateway path integrations
  - Lambda invoke permissions

### Tests
- **`backend/tests/test_get_by_name_regex.py`**
  - Comprehensive test suite with 11 test cases
  - Tests for success, failure, edge cases, and error handling
  - Mocked database and AWS dependencies

## API Endpoints

### 1. Get Artifact by Name

**Endpoint:** `GET /artifact/byName/{name}`

**Request:**
```bash
curl -X GET https://your-api.execute-api.us-east-1.amazonaws.com/dev/artifact/byName/bert-base-uncased \
  -H "X-Authorization: Bearer YOUR_TOKEN"
```

**Response (200 OK):**
```json
[
  {
    "name": "bert-base-uncased",
    "id": "12345",
    "type": "model"
  },
  {
    "name": "bert-base-uncased",
    "id": "67890",
    "type": "model"
  }
]
```

**Response (404 Not Found):**
```json
{
  "error": "No such artifact"
}
```

### 2. Get Artifact by Regex

**Endpoint:** `POST /artifact/byRegEx`

**Request:**
```bash
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/dev/artifact/byRegEx \
  -H "X-Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"regex": ".*bert.*"}'
```

**Response (200 OK):**
```json
[
  {
    "name": "bert-base-uncased",
    "id": "12345",
    "type": "model"
  },
  {
    "name": "distilbert",
    "id": "23456",
    "type": "model"
  }
]
```

**Response (400 Bad Request - Invalid Regex):**
```json
{
  "error": "Invalid regex pattern: unterminated character set at position 0"
}
```

**Response (404 Not Found):**
```json
{
  "error": "No artifact found under this regex"
}
```

## Features

### Get by Name
- ✅ Exact name matching
- ✅ Returns all artifacts with the same name (handles duplicates)
- ✅ Ordered by creation date (descending)
- ✅ Proper error handling
- ✅ CORS support

### Get by Regex
- ✅ Regular expression matching on artifact names
- ✅ Regular expression matching on README content (from metadata)
- ✅ Case-insensitive matching
- ✅ Regex validation before execution
- ✅ Comprehensive error messages
- ✅ CORS support

## Database Schema Support
Both endpoints query the `artifacts` table and return only the required metadata fields:
- `name` - Artifact name
- `id` - Unique identifier
- `type` - Artifact type (model/dataset/code)

Additional fields in the database (ratings, metadata, etc.) are fetched but not returned to match the OpenAPI spec for `ArtifactMetadata`.

## Error Handling

| Status Code | Description |
|-------------|-------------|
| 200 | Success - artifacts found |
| 400 | Bad request (missing parameters, invalid regex) |
| 403 | Authentication failed |
| 404 | No artifacts found |
| 500 | Internal server error |

## Testing
Run the test suite:
```bash
cd backend
python -m pytest tests/test_get_by_name_regex.py -v
```

## Deployment
Deploy using SAM CLI:
```bash
sam build
sam deploy
```

## OpenAPI Spec Compliance
Both endpoints comply with the autograder OpenAPI specification v3.4.6:
- Proper request/response schemas
- Correct status codes
- Required authentication headers
- Error response formats
