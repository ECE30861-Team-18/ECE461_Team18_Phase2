import json
import os
import boto3
from rds_connection import run_query

s3 = boto3.client("s3")
S3_BUCKET = os.environ.get("S3_BUCKET")

def lambda_handler(event, context):
    """Delete an artifact by its ID and type from the database."""

    token = event["headers"].get("x-authorization")
    print("Incoming event:", json.dumps(event, indent=2))

    # --- Extract path parameters from the API Gateway event ---
    path_params = event.get("pathParameters") or {}
    artifact_type = path_params.get("artifact_type")
    artifact_id = path_params.get("id")

    # --- Validate input ---
    if not artifact_type or not artifact_id: 
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing artifact_type or id in path"})
        }

    # --- Run delete query ---
    try:
        # Try to convert artifact_id to integer for DB query
        # If it fails, the ID is valid per spec regex but doesn't exist in our DB → 404
        try:
            artifact_id_int = int(artifact_id)
        except ValueError:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Artifact not found"})
            }
        
        sql = "DELETE FROM artifacts WHERE id = %s AND type = %s RETURNING id;"
        result = run_query(sql, (artifact_id_int, artifact_type), fetch=True)

        if not result:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Artifact not found"})
            }

        # ---------------------------------------------------------
        # >>> S3 DELETE ADD
        # Delete all S3 objects under prefix: <artifact_type>/<artifact_id>/
        # ---------------------------------------------------------
        prefix = f"{artifact_type}/{artifact_id}/"

        # list all objects
        listed = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)

        if "Contents" in listed:
            delete_batch = {"Objects": [{"Key": obj["Key"]} for obj in listed["Contents"]]}
            if delete_batch["Objects"]:
                s3.delete_objects(Bucket=S3_BUCKET, Delete=delete_batch)
                print(f"Deleted S3 objects under prefix: {prefix}")
        # ---------------------------------------------------------

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Artifact deleted", "deleted_id": artifact_id})
        }

    except Exception as e:
        print("❌ Error deleting artifact:", e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
