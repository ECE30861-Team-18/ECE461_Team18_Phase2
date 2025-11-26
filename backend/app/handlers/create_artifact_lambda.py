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
        token = event["headers"].get("x-authorization")
        body = json.loads(event.get("body", "{}"))
        url = body.get("url")
        provided_name = body.get("name")
        
        # NEW: Accept optional relationship info
        related_model_id = body.get("related_model_id")  # For datasets/code that belong to a model
        relationship_type = body.get("relationship_type")  # e.g., "training_dataset", "evaluation_code", "fine_tuning_dataset"
        
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
        
        # >>> MINIMAL CHANGE: type-aware URL validation <<<
        if not identifier:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid URL"})
            }

        # Allow clients to override the derived identifier with a friendly name
        if provided_name is not None:
            if not isinstance(provided_name, str) or not provided_name.strip():
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid name"})
                }
            artifact_name = provided_name.strip()
        else:
            artifact_name = identifier

        if artifact_type == "model":
            if parsed_data.category != URLCategory.HUGGINGFACE:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Model must use a Hugging Face URL"})
                }
        elif artifact_type == "dataset":
            if parsed_data.category != URLCategory.HUGGINGFACE:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Dataset must use a Hugging Face URL"})
                }
        elif artifact_type == "code":
            if parsed_data.category != URLCategory.GITHUB:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Code artifacts must use a GitHub URL"})
                }
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid artifact_type"})
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

        # >>> MINIMAL CHANGE: type-aware validity check, keep ratings as-is <<<
        if not model_obj.is_valid:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "URL is not valid"})
            }

        if artifact_type in ("model", "dataset"):
            if model_obj.category != URLCategory.HUGGINGFACE:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "URL is not a valid Hugging Face URL"})
                }
        elif artifact_type == "code":
            if model_obj.category != URLCategory.GITHUB:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "URL is not a valid GitHub URL"})
                }

        # get metadata from HF repo (README, config, tags, etc)
        repo_data = data_retriever.retrieve_data(model_obj)

        model_dict = {
            **repo_data.__dict__,
            "name": artifact_name
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
        metadata_dict = repo_data.__dict__.copy()
        metadata_dict["requested_name"] = artifact_name
        # Convert datetime objects to ISO format strings
        if metadata_dict.get('created_at'):
            metadata_dict['created_at'] = metadata_dict['created_at'].isoformat()
        if metadata_dict.get('updated_at'):
            metadata_dict['updated_at'] = metadata_dict['updated_at'].isoformat()
        metadata_json = json.dumps(metadata_dict)
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
                artifact_name,
                url,
                net_score,
                json.dumps(rating),
                "upload_pending",
                metadata_json        # <<< METADATA ADD
            ),
            fetch=True
        )

        artifact_id = result[0]['id']

        # ⭐ SPEC: construct download_url for ArtifactData ⭐
        download_url = f"s3://{S3_BUCKET}/{artifact_type}/{artifact_id}/"

        # --------------------------
        # 6b. Create lineage relationship if provided
        # --------------------------
        if related_model_id and relationship_type:
            # Validate that the related model exists
            check_model = run_query(
                "SELECT id, type FROM artifacts WHERE id = %s;",
                (related_model_id,),
                fetch=True
            )
            
            if check_model:
                # Determine relationship direction based on artifact type
                if artifact_type in ("dataset", "code"):
                    # Dataset/code -> model (they contribute to the model)
                    from_id = artifact_id
                    to_id = related_model_id
                elif artifact_type == "model":
                    # Model -> related artifact (model depends on it)
                    from_id = related_model_id
                    to_id = artifact_id
                else:
                    from_id = artifact_id
                    to_id = related_model_id
                
                # Insert relationship into artifact_relationships table
                run_query(
                    """
                    INSERT INTO artifact_relationships (from_artifact_id, to_artifact_id, relationship_type, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (from_artifact_id, to_artifact_id, relationship_type) DO NOTHING;
                    """,
                    (from_id, to_id, relationship_type, "user_provided"),
                    fetch=False
                )
                
                # Also store relationship in metadata for backward compatibility
                metadata_dict["related_artifacts"] = metadata_dict.get("related_artifacts", [])
                metadata_dict["related_artifacts"].append({
                    "artifact_id": related_model_id,
                    "relationship": relationship_type,
                    "direction": "to" if artifact_type in ("dataset", "code") else "from"
                })

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
                    "name": artifact_name,
                    "id": artifact_id,
                    "type": artifact_type
                },
                "data": {
                    "url": url,
                    "download_url": download_url   # ⭐ SPEC: include download_url in ArtifactData
                }
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
