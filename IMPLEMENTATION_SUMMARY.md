# Get By Name and Regex Implementation - Summary

## Overview
Successfully implemented two NON-BASELINE API endpoints for artifact search:
1. **GET /artifact/byName/{name}** - Search by exact name
2. **POST /artifact/byRegEx** - Search by regex pattern

## Files Created/Modified

### New Lambda Handlers
1. **backend/app/handlers/get_artifact_by_name_lambda.py**
   - Implements GET /artifact/byName/{name}
   - Returns all artifacts matching exact name
   - Returns 404 if no matches found
   - Returns 400 for invalid requests
   - Includes proper error handling

2. **backend/app/handlers/get_artifact_by_regex_lambda.py**
   - Implements POST /artifact/byRegEx
   - Searches artifact names and README content
   - Case-insensitive regex matching
   - Validates regex patterns before execution
   - Returns 404 if no matches found
   - Returns 400 for invalid regex or missing parameters

### Infrastructure Configuration
3. **template.yaml** (Modified)
   - Added `GetArtifactByNameLambda` function definition
   - Added `GetArtifactByRegexLambda` function definition
   - Configured API Gateway paths:
     - GET /artifact/byName/{name}
     - POST /artifact/byRegEx
   - Added necessary IAM permissions for RDS and Secrets Manager access

### Tests
4. **backend/tests/test_get_by_name_regex.py**
   - 11 comprehensive test cases (all passing ✅)
   - **TestGetArtifactByName** (4 tests):
     - test_get_by_name_success
     - test_get_by_name_not_found
     - test_get_by_name_missing_parameter
     - test_get_by_name_database_error
   - **TestGetArtifactByRegex** (7 tests):
     - test_get_by_regex_name_match
     - test_get_by_regex_readme_match
     - test_get_by_regex_no_match
     - test_get_by_regex_invalid_regex
     - test_get_by_regex_missing_parameter
     - test_get_by_regex_invalid_json
     - test_get_by_regex_case_insensitive

### Documentation
5. **GET_BY_NAME_REGEX_IMPLEMENTATION.md**
   - Detailed implementation guide
   - API specifications
   - Example requests/responses
   - Error handling documentation

## Test Results
```
====================================== 11 passed in 0.11s =======================================
```

All tests passing successfully!

## Key Features

### GET /artifact/byName/{name}
- **Path Parameter**: `name` (required)
- **Returns**: Array of ArtifactMetadata objects
- **Status Codes**:
  - 200: Success with artifact list
  - 400: Missing name parameter
  - 404: No artifacts found
  - 500: Server error

### POST /artifact/byRegEx
- **Request Body**: `{"regex": "pattern"}`
- **Searches**: Artifact names AND README content in metadata
- **Case-Insensitive**: Matches regardless of case
- **Returns**: Array of ArtifactMetadata objects
- **Status Codes**:
  - 200: Success with matching artifacts
  - 400: Invalid regex or missing parameter
  - 404: No matches found
  - 500: Server error

## Response Format (Both Endpoints)
```json
[
  {
    "name": "artifact-name",
    "id": "123",
    "type": "model"
  }
]
```

## Error Response Format
```json
{
  "error": "Error description"
}
```

## Technical Notes

### Database Queries
- Both handlers use parameterized SQL queries for security
- JSON fields (metadata, ratings) are properly deserialized
- Results ordered by creation date (most recent first)

### Error Handling
- Comprehensive try-catch blocks
- Regex validation before execution
- JSON parsing with error handling
- Database exception handling

### CORS Configuration
Both endpoints include proper CORS headers:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: OPTIONS,GET/POST`
- `Access-Control-Allow-Headers: Content-Type,X-Authorization`

## Testing Approach

### Mocking Strategy
- Module-level mocking for boto3, botocore, psycopg2
- Per-test mocking for `run_query` using @patch decorator
- `setup_method()` to reset module imports between tests
- Prevents test pollution and ensures clean state

### Test Coverage
- ✅ Success cases with valid data
- ✅ Error cases (404, 400, 500)
- ✅ Edge cases (empty results, invalid input)
- ✅ Validation (missing parameters, invalid JSON, bad regex)
- ✅ Feature verification (case-insensitive, README search)

## Deployment

To deploy these changes:

```bash
cd "c:\Users\Asteroid\Documents\Engineering\Year 4 (PWL)\Fall 2025\ECE 461\Project Phase 2\repo\ECE461_Team18_Phase2"

# Build
sam build

# Deploy
sam deploy --guided
```

## Next Steps

1. **Deploy to AWS** - Use SAM CLI to deploy the infrastructure
2. **Integration Testing** - Test endpoints in AWS environment
3. **Frontend Integration** - Update frontend to use new endpoints
4. **Performance Testing** - Verify regex performance with large datasets
5. **Documentation Updates** - Update API documentation with new endpoints

## Dependencies
- Python 3.11
- boto3 (AWS SDK)
- psycopg2-binary (PostgreSQL adapter)
- AWS Lambda
- Amazon RDS (PostgreSQL)
- AWS Secrets Manager
- API Gateway

## Success Criteria Met ✅
- ✅ Two new NON-BASELINE endpoints implemented
- ✅ All tests passing (11/11)
- ✅ Proper error handling
- ✅ CORS configuration
- ✅ Database integration
- ✅ Comprehensive documentation
- ✅ AWS infrastructure configured
