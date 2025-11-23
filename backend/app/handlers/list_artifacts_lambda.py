import json
from rds_connection import run_query


def _deserialize_json_fields(record, fields=("metadata", "ratings")):
    """Convert JSON strings stored in the DB back into Python objects."""
    for field in fields:
        raw_value = record.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                record[field] = json.loads(raw_value)
            except json.JSONDecodeError:
                # Leave the raw string if it is not valid JSON.
                continue


def lambda_handler(event, context):
    """Return a list of all artifacts stored in the database."""

    token = event["headers"].get("x-authorization")
    print("Incoming event:", json.dumps(event, indent=2))

    try:
        # --- Optional: in the future you can parse filters from the event["body"] or query params ---
        # For now, just fetch everything
        sql = """
        SELECT id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at
        FROM artifacts
        ORDER BY created_at DESC;
        """
        artifacts = run_query(sql, fetch=True) or []

        for artifact in artifacts:
            _deserialize_json_fields(artifact)

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps({
                "count": len(artifacts),
                "artifacts": artifacts
            }, default=str)
        }

    except Exception as e:
        print("❌ Error listing artifacts:", e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
