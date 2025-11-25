import json
from rds_connection import run_query


def _deserialize_json_fields(record, fields=("metadata", "ratings")):
    for field in fields:
        raw_value = record.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                record[field] = json.loads(raw_value)
            except json.JSONDecodeError:
                continue


def lambda_handler(event, context):
    token = event["headers"].get("x-authorization")
    print("Incoming event:", json.dumps(event, indent=2))

    try:
        # Parse the request body for query filters
        body = event.get("body", "[]")
        if isinstance(body, str):
            query_filters = json.loads(body) if body.strip() else []
        else:
            query_filters = body

        print(f"Query filters: {query_filters}")

        # Build SQL query with type filtering
        if query_filters and len(query_filters) > 0:
            # Extract artifact types from query filters
            types = []
            for query in query_filters:
                if isinstance(query, dict) and "Type" in query:
                    types.append(query["Type"])
            
            if types:
                placeholders = ", ".join(["%s"] * len(types))
                sql = f"""
                SELECT id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at
                FROM artifacts
                WHERE type IN ({placeholders})
                ORDER BY created_at DESC;
                """
                artifacts = run_query(sql, params=tuple(types), fetch=True)
            else:
                # No type filter, return all
                sql = """
                SELECT id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at
                FROM artifacts
                ORDER BY created_at DESC;
                """
                artifacts = run_query(sql, fetch=True)
        else:
            # Empty query array means return all artifacts
            sql = """
            SELECT id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at
            FROM artifacts
            ORDER BY created_at DESC;
            """
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
