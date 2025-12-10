import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rds_connection import run_query
from auth import require_auth


def _deserialize_json_fields(record, fields=("metadata", "ratings")):
    for field in fields:
        raw_value = record.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                record[field] = json.loads(raw_value)
            except json.JSONDecodeError:
                continue


def lambda_handler(event, context):
    # Validate authentication
    valid, error_response = require_auth(event)
    if not valid:
        return error_response
    
    print("Incoming event:", json.dumps(event, indent=2))

    try:
        # Parse the request body for query filters
        body = event.get("body", "[]")
        if isinstance(body, str):
            query_filters = json.loads(body) if body.strip() else []
        else:
            query_filters = body

        print(f"Query filters: {query_filters}")

        # Build SQL query with name and type filtering
        # ArtifactQuery schema: { "name": "pattern", "types": ["model", "dataset"] }
        
        where_clauses = []
        params = []
        
        if query_filters and len(query_filters) > 0:
            for query in query_filters:
                if not isinstance(query, dict):
                    continue
                
                # Handle name filtering (with wildcard support)
                name_pattern = query.get("name", "*")
                if name_pattern and name_pattern != "*":
                    # Convert wildcard * to SQL LIKE pattern %
                    sql_pattern = name_pattern.replace("*", "%")
                    where_clauses.append("name LIKE %s")
                    params.append(sql_pattern)
                
                # Handle types filtering
                types = query.get("types", [])
                if types and len(types) > 0:
                    placeholders = ", ".join(["%s"] * len(types))
                    where_clauses.append(f"type IN ({placeholders})")
                    params.extend(types)
        
        # Build final SQL query
        sql = """
        SELECT id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at
        FROM artifacts
        """
        
        if where_clauses:
            # Use OR to combine conditions from multiple queries
            sql += " WHERE " + " OR ".join(f"({clause})" for clause in where_clauses)
        
        sql += " ORDER BY created_at DESC;"
        
        print(f"Executing SQL: {sql}")
        print(f"With params: {params}")
        
        if params:
            artifacts = run_query(sql, params=tuple(params), fetch=True)
        else:
            artifacts = run_query(sql, fetch=True)

        if not artifacts:
            artifacts = []

        for artifact in artifacts:
            _deserialize_json_fields(artifact)

        # ⭐ Convert DB rows → SPEC-CORRECT ArtifactMetadata ⭐
        metadata_list = [
            {
                "name": artifact["name"],
                "id": artifact["id"],
                "type": artifact["type"]
            }
            for artifact in artifacts
        ]

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps(metadata_list, default=str)
        }

    except Exception as e:
        print("❌ Error listing artifacts:", e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
