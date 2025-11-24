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
