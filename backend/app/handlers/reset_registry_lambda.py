import json
import os
import sys
import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rds_connection import run_query
from auth import require_auth

s3 = boto3.client("s3")
S3_BUCKET = os.environ.get("S3_BUCKET")

def lambda_handler(event, context):
    # Validate authentication
    valid, error_response = require_auth(event)
    if not valid:
        return error_response
    
    try:
        # ---------------------------------------------------------
        # >>> S3 RESET ADD — delete ALL objects in the bucket
        # ---------------------------------------------------------
        listed = s3.list_objects_v2(Bucket=S3_BUCKET)

        while listed.get("Contents"):
            delete_batch = {
                "Objects": [{"Key": obj["Key"]} for obj in listed["Contents"]]
            }

            s3.delete_objects(Bucket=S3_BUCKET, Delete=delete_batch)

            # check for more pages
            if listed.get("IsTruncated"):
                listed = s3.list_objects_v2(
                    Bucket=S3_BUCKET,
                    ContinuationToken=listed["NextContinuationToken"]
                )
            else:
                break

        print("S3 bucket cleared successfully.")
        # ---------------------------------------------------------

        # Delete all artifacts from DB
        run_query("DELETE FROM artifacts;")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Registry reset successfully!"})
        }

    except Exception as e:
        print("❌ Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
