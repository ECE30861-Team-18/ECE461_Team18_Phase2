import json
import os
import boto3

from auth import require_auth
from metric_calculator import MetricCalculator
from url_handler import URLHandler
from url_category import URLCategory
from url_data import URLData
from data_retrieval import DataRetriever
from rds_connection import run_query


S3_BUCKET = os.environ.get("S3_BUCKET")
sqs_client = boto3.client("sqs")

# -----------------------------
# Lambda Handler
# -----------------------------
def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        url = body.get("url")
        artifact_type = event.get("pathParameters", {}).get("artifact_type")

        # --------------------------
        # 2. Validate request
        # --------------------------
        if not url or not artifact_type:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing URL or artifact_type"})
            }

        # Use URLHandler to extract identifier
        url_handler_temp = URLHandler()
        parsed_data = url_handler_temp.handle_url(url)
        identifier = parsed_data.unique_identifier
        
        if not identifier or parsed_data.category != URLCategory.HUGGINGFACE:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid Hugging Face URL"})
            }

        # --------------------------
        # 3. Duplicate check (using source_url)
        # --------------------------
        check_result = run_query(
            "SELECT id FROM artifacts WHERE source_url = %s AND type = %s;",
            (url, artifact_type),
            fetch=True
        )

        if check_result:
            return {
                "statusCode": 409,
                "body": json.dumps({
                    "error": "Artifact already exists",
                    "id": check_result[0]['id']
                })
            }

        # --------------------------
        # 4. RATING PIPELINE
        # --------------------------
        url_handler = URLHandler()
        data_retriever = DataRetriever(
            github_token=os.environ.get("GITHUB_TOKEN"),
            hf_token=os.environ.get("HF_TOKEN")
        )
        calc = MetricCalculator()

        # Let URLHandler build a proper URLData instance
        model_obj: URLData = url_handler.handle_url(url)

        if not model_obj.is_valid or model_obj.category != URLCategory.HUGGINGFACE:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "URL is not a valid Hugging Face URL"})
            }

        # get metadata from HF repo (README, config, tags, etc)
        repo_data = data_retriever.retrieve_data(model_obj)

        model_dict = {
            **repo_data.__dict__,
            "name": identifier
        }

        rating = calc.calculate_all_metrics(model_dict, category="MODEL")
        net_score = rating["net_score"]

        # ### --------------------------
        # ### 5. Reject if disqualified
        # ### --------------------------
        # if net_score < 0.5:
        #     result = run_query(
        #         """
        #         INSERT INTO artifacts (type, name, source_url, net_score, ratings, status)
        #         VALUES (%s, %s, %s, %s, %s, %s)
        #         RETURNING id;
        #         """,
        #         (artifact_type, identifier, url, net_score, json.dumps(rating), "disqualified"),
        #         fetch=True
        #     )

        #     artifact_id = result[0]['id']

        #     return {
        #         "statusCode": 424,  # FAILED_DEPENDENCY
        #         "body": json.dumps({
        #             "error": "Artifact disqualified by rating",
        #             "net_score": net_score,
        #             "id": artifact_id
        #         })
        #     }

        # ---------------------------------------------------------
        # >>> METADATA ADD — serialize HuggingFace metadata
        # ---------------------------------------------------------
        metadata_json = json.dumps(repo_data.__dict__)
        # ---------------------------------------------------------

        # --------------------------
        # 6. Insert as upload_pending
        # --------------------------
        result = run_query(
            """
            INSERT INTO artifacts (type, name, source_url, net_score, ratings, status, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                artifact_type,
                identifier,
                url,
                net_score,
                json.dumps(rating),
                "upload_pending",
                metadata_json        # <<< METADATA ADD
            ),
            fetch=True
        )

        artifact_id = result[0]['id']

        # --------------------------
        # 7. Send SQS message to ECS ingest worker
        # --------------------------
        sqs_client.send_message(
            QueueUrl=os.environ.get("INGEST_QUEUE_URL"),
            MessageBody=json.dumps({
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "identifier": identifier,
                "source_url": url
            })
        )

        # --------------------------
        # 8. SUCCESS (201)
        # --------------------------
        return {
            "statusCode": 201,
            "body": json.dumps({
                "metadata": {
                    "name": identifier,
                    "id": artifact_id,
                    "type": artifact_type
                },
                "data": {
                    "url": url
                }
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
