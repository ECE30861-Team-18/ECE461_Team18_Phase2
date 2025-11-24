# Sample API Test Commands

Replace `YOUR_API_URL` with your actual API Gateway URL from the CloudFormation outputs.

## PowerShell Commands

### Test GET /artifact/byName/{name}

```powershell
# Search for artifact named "bert"
Invoke-RestMethod -Uri "YOUR_API_URL/artifact/byName/bert" `
  -Method Get `
  -Headers @{"X-Authorization"="bearer YOUR_TOKEN"} `
  -ContentType "application/json"

# Search for artifact named "whisper"
Invoke-RestMethod -Uri "YOUR_API_URL/artifact/byName/whisper" `
  -Method Get `
  -Headers @{"X-Authorization"="bearer YOUR_TOKEN"} `
  -ContentType "application/json"
```

### Test POST /artifact/byRegEx

```powershell
# Search using regex pattern
$body = @{
  regex = ".*bert.*"
} | ConvertTo-Json

Invoke-RestMethod -Uri "YOUR_API_URL/artifact/byRegEx" `
  -Method Post `
  -Headers @{"X-Authorization"="bearer YOUR_TOKEN"; "Content-Type"="application/json"} `
  -Body $body

# Search with alternation pattern
$body = @{
  regex = ".*?(audience|classifier).*"
} | ConvertTo-Json

Invoke-RestMethod -Uri "YOUR_API_URL/artifact/byRegEx" `
  -Method Post `
  -Headers @{"X-Authorization"="bearer YOUR_TOKEN"; "Content-Type"="application/json"} `
  -Body $body
```

## curl Commands (Git Bash / Linux / macOS)

### Test GET /artifact/byName/{name}

```bash
# Search for artifact named "bert"
curl -X GET "YOUR_API_URL/artifact/byName/bert" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"

# Search for artifact named "whisper"
curl -X GET "YOUR_API_URL/artifact/byName/whisper" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### Test POST /artifact/byRegEx

```bash
# Search using regex pattern
curl -X POST "YOUR_API_URL/artifact/byRegEx" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"regex": ".*bert.*"}'

# Search with alternation pattern
curl -X POST "YOUR_API_URL/artifact/byRegEx" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"regex": ".*?(audience|classifier).*"}'

# Search for artifacts starting with "whisper"
curl -X POST "YOUR_API_URL/artifact/byRegEx" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"regex": "^whisper.*"}'
```

## Test Error Handling

### Test invalid regex (should return 400)

```powershell
# PowerShell
$body = @{
  regex = "[invalid(regex"
} | ConvertTo-Json

Invoke-RestMethod -Uri "YOUR_API_URL/artifact/byRegEx" `
  -Method Post `
  -Headers @{"X-Authorization"="bearer YOUR_TOKEN"; "Content-Type"="application/json"} `
  -Body $body
```

```bash
# curl
curl -X POST "YOUR_API_URL/artifact/byRegEx" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"regex": "[invalid(regex"}'
```

### Test missing regex field (should return 400)

```powershell
# PowerShell
$body = @{} | ConvertTo-Json

Invoke-RestMethod -Uri "YOUR_API_URL/artifact/byRegEx" `
  -Method Post `
  -Headers @{"X-Authorization"="bearer YOUR_TOKEN"; "Content-Type"="application/json"} `
  -Body $body
```

```bash
# curl
curl -X POST "YOUR_API_URL/artifact/byRegEx" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Expected Responses

### Successful Response (200)

```json
[
  {
    "name": "bert-base-uncased",
    "id": "1234567890",
    "type": "model"
  },
  {
    "name": "bert-large-uncased",
    "id": "1234567891",
    "type": "model"
  }
]
```

### Not Found (404)

```json
{
  "error": "No such artifact"
}
```

or

```json
{
  "error": "No artifact found under this regex"
}
```

### Bad Request (400)

```json
{
  "error": "Missing artifact name in path"
}
```

or

```json
{
  "error": "Invalid regex pattern: unterminated character set at position 0"
}
```

## Quick Tips

1. **Get your API URL**: After deploying, run:
   ```powershell
   aws cloudformation describe-stacks --stack-name ece461-team-18-phase-2-stack --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text
   ```

2. **Without authentication**: If your endpoints don't require auth, remove the `X-Authorization` header:
   ```bash
   curl -X GET "YOUR_API_URL/artifact/byName/bert"
   ```

3. **Pretty print JSON in PowerShell**:
   ```powershell
   Invoke-RestMethod -Uri "YOUR_API_URL/artifact/byName/bert" | ConvertTo-Json -Depth 10
   ```

4. **Pretty print JSON with curl**:
   ```bash
   curl -X GET "YOUR_API_URL/artifact/byName/bert" | jq '.'
   ```
