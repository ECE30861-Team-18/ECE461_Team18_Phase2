# Dataset and Code Repository Linkage Implementation

## Overview

This implementation establishes relationships between models, datasets, and code repositories in accordance with the OpenAPI spec's **lineage graph** requirement (BASELINE feature).

---

## Architecture

### 1. **Independent Artifact Ingestion**
Each artifact (model/dataset/code) is ingested separately with its own unique `artifact_id`:
- Models: `POST /artifact/model`
- Datasets: `POST /artifact/dataset`  
- Code: `POST /artifact/code`

### 2. **Relationship Tracking**
Relationships are tracked through:
- **Primary**: `artifact_relationships` table (normalized relational approach)
- **Secondary**: `metadata` JSONB field in `artifacts` table (for backward compatibility)

### 3. **Lineage Graph Retrieval**
The `/artifact/model/{id}/lineage` endpoint (BASELINE) returns:
```json
{
  "nodes": [
    {
      "artifact_id": "3847247294",
      "name": "audience-classifier",
      "source": "config_json"
    },
    {
      "artifact_id": "5738291045",
      "name": "bookcorpus",
      "source": "user_provided"
    }
  ],
  "edges": [
    {
      "from_node_artifact_id": "5738291045",
      "to_node_artifact_id": "3847247294",
      "relationship": "training_dataset"
    }
  ]
}
```

---

## Database Schema

### `artifacts` Table (existing)
```sql
CREATE TABLE artifacts (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT,
    source_url TEXT NOT NULL,
    download_url TEXT,
    net_score FLOAT,
    ratings JSONB,
    status TEXT DEFAULT 'upload_pending',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `artifact_relationships` Table (new)
```sql
CREATE TABLE artifact_relationships (
    id SERIAL PRIMARY KEY,
    from_artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    to_artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(from_artifact_id, to_artifact_id, relationship_type)
);
```

**Indexes:**
- `idx_relationships_from` on `from_artifact_id`
- `idx_relationships_to` on `to_artifact_id`

---

## Usage Examples

### Example 1: Ingest Model with Dataset

**Step 1: Create the model**
```bash
POST /artifact/model
{
  "url": "https://huggingface.co/my-org/my-model",
  "name": "audience-classifier"
}

# Response: { "metadata": { "id": "3847247294", ... } }
```

**Step 2: Create the dataset and link it**
```bash
POST /artifact/dataset
{
  "url": "https://huggingface.co/datasets/bookcorpus",
  "name": "bookcorpus",
  "related_model_id": "3847247294",
  "relationship_type": "training_dataset"
}

# Response: { "metadata": { "id": "5738291045", ... } }
```

**Step 3: Create code repository and link it**
```bash
POST /artifact/code
{
  "url": "https://github.com/my-org/training-code",
  "name": "training-scripts",
  "related_model_id": "3847247294",
  "relationship_type": "training_code"
}

# Response: { "metadata": { "id": "9182736455", ... } }
```

**Step 4: Retrieve lineage graph**
```bash
GET /artifact/model/3847247294/lineage

# Response:
{
  "nodes": [
    { "artifact_id": "3847247294", "name": "audience-classifier", "source": "database" },
    { "artifact_id": "5738291045", "name": "bookcorpus", "source": "user_provided" },
    { "artifact_id": "9182736455", "name": "training-scripts", "source": "user_provided" }
  ],
  "edges": [
    {
      "from_node_artifact_id": "5738291045",
      "to_node_artifact_id": "3847247294",
      "relationship": "training_dataset"
    },
    {
      "from_node_artifact_id": "9182736455",
      "to_node_artifact_id": "3847247294",
      "relationship": "training_code"
    }
  ]
}
```

---

## Relationship Types

### Standard Relationship Types
- `training_dataset` - Dataset used to train the model
- `evaluation_dataset` - Dataset used to evaluate the model
- `fine_tuning_dataset` - Dataset used for fine-tuning
- `training_code` - Code used to train the model
- `evaluation_code` - Code used to evaluate the model
- `inference_code` - Code used for model inference
- `base_model` - The base model this model was derived from

### Custom Types
Users can provide custom relationship types as needed.

---

## API Specification Compliance

### ✅ BASELINE Features
1. **Separate artifact endpoints**: `/artifact/{type}` for model/dataset/code
2. **Lineage graph endpoint**: `/artifact/model/{id}/lineage`
3. **Metadata storage**: Relationships stored in `metadata` JSONB field
4. **Graph structure**: Returns nodes and edges as per spec

### ✅ Spec Adherence
1. Each artifact gets a unique `artifact_id`
2. Artifacts can share names but have different IDs
3. Lineage extracted from structured metadata
4. Support for provenance tracking (`source` field)

---

## Rating Integration

The rating system considers linked datasets and code:

```python
# In create_artifact_lambda.py
model_dict = {
    **repo_data.__dict__,
    "name": artifact_name,
    "code_present": bool(related_code_id),
    "dataset_present": bool(related_dataset_id)
}

rating = calc.calculate_all_metrics(model_dict, category="MODEL")
```

The `dataset_quality` and `code_quality` metrics use these flags.

---

## Migration Steps

### 1. Update Database
```bash
python backend/init_db.py
```

### 2. Deploy Lambda Functions
```bash
sam build
sam deploy --guided
```

### 3. Test Endpoints
```bash
# Test creating linked artifacts
python test_artifact_relationships.py
```

---

## Future Enhancements

1. **Automatic relationship discovery**: Extract relationships from HuggingFace metadata
2. **Dependency resolution**: Calculate transitive dependencies
3. **Cost tracking**: Include dependency costs in `/artifact/{type}/{id}/cost`
4. **Audit trail**: Track relationship creation/deletion in audit log

---

## Files Modified

1. `backend/init_db.py` - Added `artifact_relationships` table
2. `backend/app/handlers/create_artifact_lambda.py` - Added relationship handling
3. `backend/app/handlers/get_lineage_lambda.py` - New lineage retrieval handler
4. `template.yaml` - Added lineage endpoint and Lambda configuration

---

## Backward Compatibility

- Existing artifacts without relationships continue to work
- `related_model_id` and `relationship_type` are optional parameters
- Old ingestion workflows remain unchanged
- Lineage endpoint returns empty graph for unlinked artifacts
