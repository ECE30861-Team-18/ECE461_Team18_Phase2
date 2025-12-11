# ECE461 Team 18 Phase 2 - ML Model Registry

## What This System Does

A serverless ML model registry that evaluates, stores, and manages machine learning models from HuggingFace and GitHub repositories. The system provides quality scoring, metadata management, search capabilities, and model lineage tracking through a REST API and React web interface.

## System Components

### Backend Infrastructure (AWS)
- **16 Lambda Functions** - Python 3.11 serverless handlers
- **API Gateway** - REST API endpoints  
- **RDS PostgreSQL** - Metadata and authentication database
- **S3** - Model artifact storage
- **Secrets Manager** - Database credentials
- **CloudWatch** - Application logs

### Frontend
- **React.js** - Web UI for model ingestion and browsing
- **Bootstrap-styled** - Responsive design

### Core Modules
- **`auth.py`** - JWT token generation and validation
- **`url_handler.py`** - GitHub/HuggingFace URL parsing
- **`data_retrieval.py`** - External API clients for model metadata
- **`metric_calculator.py`** - Quality metric orchestration
- **`submetrics.py`** - 11 individual metric implementations
- **`rds_connection.py`** - PostgreSQL database interface

## API Endpoints (16 Handlers)

### Authentication
```
PUT /authenticate
```
Returns JWT token for authenticated requests. Tokens valid for 10 hours or 1000 API calls.

**Default User**: `ece30861defaultadminuser` / `correcthorsebatterystaple123(!__+@**(A'"`;DROP TABLE packages;`

### Model Management
```
POST   /artifacts                    - Ingest model from URL
GET    /artifacts/{type}              - List all artifacts
GET    /artifacts/{type}/{id}         - Download artifact
PUT    /artifacts/{type}/{id}         - Update metadata
DELETE /artifacts/{type}/{id}         - Delete artifact
```

### Search
```
GET  /artifact/byName?name={name}     - Exact name search
POST /artifact/byRegEx                - Regex pattern search
```

### Analysis
```
GET  /artifact/model/{id}/rate        - Calculate quality metrics
GET  /artifact/model/{id}/lineage     - Get dependency graph  
POST /artifact/model/{id}/license-check - Check license compatibility
GET  /artifact/{type}/{id}/cost       - Calculate storage cost
```

### System
```
GET    /health                         - Health check
GET    /health/components              - Detailed component status
GET    /tracks                         - Planned features
DELETE /reset                          - Clear registry (admin only)
```

## Quality Metrics (11 Total)

The system calculates these metrics for every model:

1. **Size Compatibility** - Hardware platform scoring (Pi/Jetson/Desktop/Server)
2. **License Score** - LGPL v2.1 compatibility check
3. **Ramp-Up Time** - Documentation quality (README evaluation)
4. **Bus Factor** - Contributor concentration risk
5. **Dataset Quality** - Training data documentation score
6. **Code Quality** - Code examples and usability
7. **Dataset & Code Availability** - Combined availability metric
8. **Performance Claims** - AI-powered benchmark validation (AWS Bedrock)
9. **Reproducibility** - Automated code execution testing
10. **Reviewedness** - PR code review coverage percentage
11. **TreeScore** - Average quality score of all parent models in lineage graph

**Net Score**: Weighted average of metrics 1-10 (TreeScore is informational only, not included in net_score)

## Database Schema

### Tables (5)

**`artifacts`** - Core model registry
```sql
id, type, name, source_url, download_url, net_score, 
ratings (JSONB), status, metadata (JSONB), created_at
```

**`users`** - Authentication
```sql
id, username, password_hash, is_admin, created_at
```

**`auth_tokens`** - JWT tracking
```sql
id, token, username, expires_at, created_at
```

**`artifact_relationships`** - Model lineage
```sql
id, from_artifact_id, to_artifact_id, relationship_type, source, created_at
```

**`artifact_dependencies`** - Dataset/code links
```sql
id, model_id, artifact_id, model_name, dependency_name, 
dependency_type, source, created_at
```

## Project Structure

```
backend/
├── app/
│   ├── handlers/              # Lambda functions (16)
│   │   ├── auth_lambda.py
│   │   ├── create_artifact_lambda.py
│   │   ├── list_artifacts_lambda.py
│   │   ├── get_artifact_lambda.py
│   │   ├── update_artifact_lambda.py
│   │   ├── delete_artifact_lambda.py
│   │   ├── get_artifact_by_name_lambda.py
│   │   ├── get_artifact_by_regex_lambda.py
│   │   ├── rate_artifact_lambda.py
│   │   ├── cost_artifact_lambda.py
│   │   ├── get_lineage_lambda.py
│   │   ├── license_check_lambda.py
│   │   ├── reset_registry_lambda.py
│   │   ├── health_lambda.py
│   │   ├── health_components_lambda.py
│   │   └── tracks_lambda.py
│   ├── auth.py                # JWT implementation
│   ├── url_handler.py         # URL parsing
│   ├── data_retrieval.py      # GitHub/HF API clients
│   ├── metric_calculator.py   # Metric orchestration
│   ├── submetrics.py          # 11 metric classes
│   ├── metric.py              # Base metric interface
│   ├── rds_connection.py      # Database utilities
│   ├── cli_controller.py      # Legacy CLI (Phase 1)
│   └── main.py                # CLI entry point
├── tests/                     # 226 tests (30 files)
│   ├── test_*_lambda.py       # Handler tests (13 files)
│   ├── test_auth*.py          # Auth tests (2 files)
│   ├── test_metrics.py        # Metric tests
│   ├── test_submetrics.py     # Individual metrics
│   ├── test_url_handler*.py   # URL parsing (4 files)
│   ├── test_data_retrieval.py
│   ├── test_integration.py
│   └── test_*.py              # Additional coverage
├── init_db.py                 # Database schema creation
└── requirements.txt

frontend/
├── src/
│   ├── pages/
│   │   ├── Home.js            # Dashboard
│   │   └── Ingest.js          # Model upload UI
│   ├── components/
│   │   └── Navbar.js
│   ├── App.js
│   └── index.js
└── package.json

template.yaml                  # AWS SAM deployment
autograder_openapi_spec.yaml   # API specification
```

## How It Works

### 1. Model Ingestion Flow
```
User submits HF URL → create_artifact_lambda receives request
→ Validates auth → Checks URL format → Fetches metadata from HuggingFace
→ Calculates 10 quality metrics → Checks if net_score ≥ 0.5
→ Uploads to S3 → Stores metadata in RDS → Returns artifact ID
```

### 2. Quality Scoring Pipeline
```
rate_artifact_lambda → metric_calculator.py orchestrates
→ Spawns 11 metric instances from submetrics.py
→ Each metric fetches data from GitHub/HF APIs
→ Calculates score (0.0-1.0) + latency
→ Aggregates into net_score (weighted average)
→ Stores in artifacts.ratings (JSONB)
```

### 3. Search Operations
```
byName: SQL LIKE query on artifacts.name
byRegEx: PostgreSQL regex (name ~* pattern OR metadata::text ~* pattern)
```

### 4. Authentication Flow
```
/authenticate → Validates username/password → Hashes password (SHA256)
→ Checks users table → Generates JWT token → Stores in auth_tokens
→ Returns "bearer <token>" → Used in X-Authorization header
```

## Deployment

### Prerequisites
- AWS CLI configured
- SAM CLI installed
- Python 3.11
- PostgreSQL (for init_db.py)

### Steps

**1. Create Secrets Manager secret**
```bash
aws secretsmanager create-secret --name DB_CREDS \
  --secret-string '{"DB_HOST":"your-rds-endpoint","DB_PORT":"5432","DB_NAME":"postgres","DB_USER":"postgres","DB_PASS":"password"}'
```

**2. Deploy SAM app**
```bash
cd ECE461_Team18_Phase2
sam build
sam deploy --guided
# Provide GITHUBTOKEN and HFTOKEN parameters
```

**3. Initialize database**
```bash
cd backend
python init_db.py  # Creates 5 tables + default user
```

**4. Verify**
```bash
curl https://your-api-url/health
```

### Environment Variables
Set in `template.yaml`:
- `S3_BUCKET` - Model storage bucket
- `SECRET_NAME` - DB_CREDS
- `GITHUB_TOKEN` - GitHub API access
- `HF_TOKEN` - HuggingFace API access
- `LOG_LEVEL` - 0/1/2 (silent/info/debug)

## Testing

### Run All Tests (226 total)
```bash
cd backend
pytest tests/ -v
```

### Test Breakdown
- **Handler tests**: 13 files, 27 tests (Lambda functions)
- **Auth tests**: 2 files, 23 tests (JWT, database auth)
- **Metric tests**: 3 files, 27 tests (quality calculations)
- **URL handler tests**: 4 files, 58 tests (GitHub/HF parsing)
- **Integration tests**: 11 tests (end-to-end)
- **Utility tests**: 80+ tests (CLI, data retrieval, etc.)

### Coverage
```bash
pytest tests/ --cov=app --cov-report=html
# Opens htmlcov/index.html
```

## Key Implementation Details

### Metric Calculation (`submetrics.py`)
Each metric is a class inheriting from `Metric`:
- `SizeMetric` - Parses safetensors.index.json for model size
- `LicenseMetric` - Extracts license from model card
- `RampUpMetric` - Evaluates README quality (baseline 0.25)
- `BusFactorMetric` - Analyzes GitHub commit distribution
- `DatasetQualityMetric` - Term matching in documentation (baseline 0.25)
- `CodeQualityMetric` - Code example presence (baseline 0.30)
- `AvailableScoreMetric` - Dataset + code availability (0.50 weights)
- `PerformanceMetric` - AWS Bedrock AI analysis of benchmarks
- `ReproducibilityMetric` - Extracts/executes Python snippets from README
- `ReviewednessMetric` - GitHub PR review coverage via API
- `TreeScoreMetric` - Average net_score of all parent models from lineage graph

### URL Parsing (`url_handler.py`)
```python
URLHandler.handle_url(url) → URLData object
  .is_valid: bool
  .owner: str
  .repository: str
  .category: 'github' | 'huggingface'
  .unique_identifier: 'owner/repo'
```

### Data Retrieval (`data_retrieval.py`)
Two API clients:
- `GitHubAPIClient` - Repository metadata, commits, PRs, reviews
- `HuggingFaceClient` - Model cards, configs, file lists

### Database Operations (`rds_connection.py`)
```python
run_query(sql, params=None, fetch=False, fetch_one=False)
# Uses psycopg2 with RealDictCursor for dict results
```

### Authentication (`auth.py`)
```python
generate_token(username, is_admin) → JWT string
require_auth(event) → (bool, error_response | None)
# Validates X-Authorization header against auth_tokens table
```

## API Usage Examples

### Authenticate
```bash
curl -X PUT https://api-url/authenticate \
  -H "Content-Type: application/json" \
  -d '{"User":{"name":"ece30861defaultadminuser","isAdmin":true},"Secret":{"password":"correcthorsebatterystaple123(!__+@**(A'\''\"`;DROP TABLE packages;"}}'
# Returns: "bearer eyJhbGc..."
```

### Ingest Model
```bash
curl -X POST https://api-url/artifacts \
  -H "X-Authorization: bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"type":"model","URL":"https://huggingface.co/bert-base-uncased","JSProgram":""}'
```

### Rate Model
```bash
curl https://api-url/artifacts/model/123/rate \
  -H "X-Authorization: bearer <token>"
# Returns: {"net_score": 0.75, "size_score": 0.8, "license": 1.0, ...}
```

### Search by Regex
```bash
curl -X POST https://api-url/artifact/byRegEx \
  -H "X-Authorization: bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"RegEx":"bert.*uncased"}'
```

## Development Notes

### Adding New Metrics
1. Create class in `submetrics.py` inheriting from `Metric`
2. Implement `calculate_metric()` method
3. Add to `metric_calculator.py` metric list
4. Update net score weights

### Adding New Endpoints
1. Create `new_handler_lambda.py` in `handlers/`
2. Add Lambda function in `template.yaml`
3. Add API Gateway route
4. Create `test_new_handler_lambda.py` in `tests/`

### Local Testing
```python
# Mock AWS services
import sys
from unittest.mock import MagicMock
sys.modules['boto3'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()

# Import and test
from handlers.auth_lambda import lambda_handler
result = lambda_handler(event, None)
```

## Troubleshooting

### Common Issues

**"Repository not found" errors**
- Check `GITHUB_TOKEN` is set correctly
- Verify GitHub URL format: `https://github.com/owner/repo`
- Check GitHub API rate limits: `curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit`

**Database connection timeouts**
- Verify RDS security group allows Lambda access (port 5432)
- Check `DB_CREDS` secret exists in Secrets Manager
- Confirm RDS instance is "available" status

**"Package does not meet quality standards"**
- Model net_score must be ≥ 0.5
- Check individual metric scores with `/rate` endpoint
- Review metric baselines in `submetrics.py`

**Lambda function timeouts**
- Increase timeout in `template.yaml` (currently 10-30s)
- Large models may need longer timeout for S3 operations
- Check CloudWatch logs for specific bottleneck

### CloudWatch Logs
Each Lambda has dedicated log group:
```
/aws/lambda/ece461Ph2-<HandlerName>
```

View recent errors:
```bash
aws logs tail /aws/lambda/ece461Ph2-CreateArtifactLambda --follow --filter-pattern ERROR
```

## Team

**ECE461 Team 18** - Fall 2025  
Academic project for Software Engineering course

---

*Built with AWS Lambda, Python 3.11, PostgreSQL and React.*