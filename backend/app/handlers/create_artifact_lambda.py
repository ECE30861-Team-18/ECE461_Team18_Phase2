import json
import os
import boto3
import traceback   # <<< NEW

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

    # ⭐ SUPER-LOG EVERYTHING ⭐
    print("\n\n================= CREATE ARTIFACT LAMBDA CALLED =================")
    print("RAW EVENT:\n", json.dumps(event, indent=2))
    print("================================================================\n")

    try:
        # HEADER / TOKEN LOGGING
        print("HEADERS:", json.dumps(event.get("headers", {}), indent=2))

        token = event["headers"].get("x-authorization")

        # BODY LOGGING
        body_raw = event.get("body", "{}")
        print("RAW BODY:", body_raw)

        body = json.loads(body_raw)
        print("PARSED BODY:", json.dumps(body, indent=2))

        url = body.get("url")
        path_params = event.get("pathParameters", {})
        print("PATH PARAMS:", json.dumps(path_params, indent=2))

        artifact_type = path_params.get("artifact_type")
        print("artifact_type =", artifact_type)
        print("submitted URL =", url)

        # --------------------------
        # 2. Validate request
        # --------------------------
        if not url or not artifact_type:
            print("❌ Missing URL or artifact_type")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing URL or artifact_type"})
            }

        # Extract identifier
        url_handler_temp = URLHandler()
        parsed_data = url_handler_temp.handle_url(url)

        print("\n------ URL PARSED DATA ------")
        print(json.dumps(parsed_data.__dict__, indent=2))
        print("------------------------------\n")

        identifier = parsed_data.unique_identifier
        print("identifier =", identifier)

        # >>> MINIMAL CHANGE: type-aware URL validation <<<
        if not identifier:
            print("❌ No identifier extracted")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid URL"})
            }

        # Type checks
        print("Checking artifact type rules...")
        if artifact_type == "model":
            if parsed_data.category != URLCategory.HUGGINGFACE:
                print("❌ model requires HF URL")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Model must use a Hugging Face URL"})
                }
        elif artifact_type == "dataset":
            if parsed_data.category != URLCategory.HUGGINGFACE:
                print("❌ dataset requires HF URL")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Dataset must use a Hugging Face URL"})
                }
        elif artifact_type == "code":
            if parsed_data.category != URLCategory.GITHUB:
                print("❌ code requires GitHub URL")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Code artifacts must use a GitHub URL"})
                }
        else:
            print("❌ invalid artifact_type =", artifact_type)
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid artifact_type"})
            }

        # --------------------------
        # 3. Duplicate check
        # --------------------------
        print("Checking for duplicates in DB...")
        check_result = run_query(
            "SELECT id FROM artifacts WHERE source_url = %s AND type = %s;",
            (url, artifact_type),
            fetch=True
        )
        print("duplicate check result:", check_result)

        if check_result:
            print("❌ DUPLICATE DETECTED")
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
        print("\n▶ Running rating pipeline...")
        url_handler = URLHandler()
        data_retriever = DataRetriever(
            github_token=os.environ.get("GITHUB_TOKEN"),
            hf_token=os.environ.get("HF_TOKEN")
        )
        calc = MetricCalculator()

        model_obj: URLData = url_handler.handle_url(url)
        print("URLData after handle_url():")
        print(json.dumps(model_obj.__dict__, indent=2))

        if not model_obj.is_valid:
            print("❌ URL is not valid")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "URL is not valid"})
            }

        print("Retrieving repo_data...")
        repo_data = data_retriever.retrieve_data(model_obj)
        print("repo_data retrieved successfully")

        model_dict = { **repo_data.__dict__, "name": identifier }

        print("Running metric calculator...")
        rating = calc.calculate_all_metrics(model_dict, category="MODEL")
        print("Rating output:", json.dumps(rating, indent=2))

        net_score = rating["net_score"]
        print("Net score =", net_score)

        # --------------------------
        # METADATA SERIALIZATION
        # --------------------------
        metadata_dict = repo_data.__dict__.copy()
        if metadata_dict.get('created_at'):
            metadata_dict['created_at'] = metadata_dict['created_at'].isoformat()
        if metadata_dict.get('updated_at'):
            metadata_dict['updated_at'] = metadata_dict['updated_at'].isoformat()

        metadata_json = json.dumps(metadata_dict)
        print("Final metadata JSON:", metadata_json)

        # --------------------------
        # 6. INSERT INTO DB
        # --------------------------
        print("Inserting new artifact into DB...")
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
                metadata_json
            ),
            fetch=True
        )

        print("Insert result:", result)
        artifact_id = result[0]['id']

        download_url = f"s3://{S3_BUCKET}/{artifact_type}/{artifact_id}/"
        print("Constructed download_url:", download_url)

        # --------------------------
        # 7. SQS MESSAGE
        # --------------------------
        print("Sending SQS ingest message...")
        sqs_body = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "identifier": identifier,
            "source_url": url
        }
        print("SQS BODY:", json.dumps(sqs_body, indent=2))

        sqs_client.send_message(
            QueueUrl=os.environ.get("INGEST_QUEUE_URL"),
            MessageBody=json.dumps(sqs_body)
        )

        print("SQS message sent.")

        # --------------------------
        # 8. SUCCESS RESPONSE
        # --------------------------
        response_body = {
            "metadata": {
                "name": identifier,
                "id": artifact_id,
                "type": artifact_type
            },
            "data": {
                "url": url,
                "download_url": download_url
            }
        }

        print("\nFINAL RESPONSE:")
        print(json.dumps(response_body, indent=2))

        return {
            "statusCode": 201,
            "body": json.dumps(response_body)
        }

    except Exception as e:
        print("\n❌ EXCEPTION CAUGHT:")
        print(str(e))
        traceback.print_exc()

        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
