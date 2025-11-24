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

    path_params = event.get("pathParameters") or {}
    artifact_type = path_params.get("artifact_type")
    artifact_id = path_params.get("id")

    if not artifact_type or not artifact_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing artifact_type or id in path"})
        }

    try:
        sql = """
        SELECT id, type, name, source_url, download_url, net_score, ratings, status, metadata, created_at
        FROM artifacts
        WHERE id = %s AND type = %s;
        """
        results = run_query(sql, (artifact_id, artifact_type), fetch=True)

        if not results:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Artifact not found"})
            }

        artifact = results[0]
        _deserialize_json_fields(artifact)

        # ⭐ REQUIRED AUTOGRADER FORMAT ⭐
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "metadata": {
                    "id": artifact["id"],
                    "type": artifact["type"],
                    "name": artifact["name"],
                    "source_url": artifact["source_url"],
                    "download_url": artifact["download_url"],
                    "net_score": artifact["net_score"],
                    "status": artifact["status"],
                    "ratings": artifact["ratings"],
                    "metadata": artifact["metadata"],
                    "created_at": artifact["created_at"]
                }
            }, default=str)
        }

    except Exception as e:
        print("❌ Error fetching artifact:", e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
