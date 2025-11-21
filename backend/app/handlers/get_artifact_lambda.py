import json
from rds_connection import run_query


def lambda_handler(event, context):
    """Retrieve an artifact by its ID and type from the database."""

    token = event["headers"].get("x-authorization")
    print("Incoming event:", json.dumps(event, indent=2))

    # --- Extract parameters from URL path ---
    path_params = event.get("pathParameters") or {}
    artifact_type = path_params.get("artifact_type")
    artifact_id = path_params.get("id")

    if not artifact_type or not artifact_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing artifact_type or id in path"})
        }

    # --- Fetch from database ---
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

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Artifact retrieved successfully",
                "artifact": artifact
            }, default=str)
        }

    except Exception as e:
        print("❌ Error fetching artifact:", e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
