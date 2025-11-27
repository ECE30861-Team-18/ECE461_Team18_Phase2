import json
import os
import boto3
import traceback   # <<< LOGGING

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
# LOGGING HELPERS
# -----------------------------
def log_event(event, context):  # <<< LOGGING
    print("==== INCOMING EVENT ====")
    try:
        print(json.dumps(event, indent=2))
    except:
        print(event)

    print("==== CONTEXT ====")
    try:
        print(json.dumps({
            "aws_request_id": context.aws_request_id,
            "function_name": context.function_name,
            "memory_limit_in_mb": context.memory_limit_in_mb,
            "function_version": context.function_version
        }, indent=2))
    except:
        pass

def log_response(response):  # <<< LOGGING
    print("==== OUTGOING RESPONSE ====")
    try:
        print(json.dumps(response, indent=2))
    except:
        print(response)

def log_exception(e):  # <<< LOGGING
    print("==== EXCEPTION OCCURRED ====")
    print(str(e))
    traceback.print_exc()


# -----------------------------
# Lambda Handler
# -----------------------------
def lambda_handler(event, context):

    log_event(event, context)  # <<< LOGGING

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
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing URL or artifact_type"})
            }
            log_response(response)  # <<< LOGGING
            return response

        # Use URLHandler to extract identifier
        url_handler_temp = URLHandler()
        parsed_data = url_handler_temp.handle_url(url)
        identifier = parsed_data.unique_identifier
        
        # >>> MINIMAL CHANGE: type-aware URL validation <<<
        if not identifier:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid URL"})
            }
            log_response(response)  # <<< LOGGING
            return response

        # Allow clients to override the derived identifier with a friendly name
        if provided_name is not None:
            if not isinstance(provided_name, str) or not provided_name.strip():
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid name"})
                }
                log_response(response)  # <<< LOGGING
                return response
            artifact_name = provided_name.strip()
        else:
            artifact_name = identifier

        if artifact_type == "model":
            if parsed_data.category != URLCategory.HUGGINGFACE:
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Model must use a Hugging Face URL"})
                }
                log_response(response)  # <<< LOGGING
                return response
        elif artifact_type == "dataset":
            if parsed_data.category not in (URLCategory.HUGGINGFACE, URLCategory.GITHUB, URLCategory.KAGGLE):
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Dataset must use a Hugging Face, GitHub, or Kaggle URL"})
                }
                log_response(response)  # <<< LOGGING
                return response
        elif artifact_type == "code":
            if parsed_data.category != URLCategory.GITHUB:
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Code artifacts must use a GitHub URL"})
                }
                log_response(response)  # <<< LOGGING
                return response
        else:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid artifact_type"})
            }
            log_response(response)  # <<< LOGGING
            return response

        # --------------------------
        # 3. Duplicate check (using source_url)
        # --------------------------
        check_result = run_query(
            "SELECT id FROM artifacts WHERE source_url = %s AND type = %s;",
            (url, artifact_type),
            fetch=True
        )

        if check_result:
            response = {
                "statusCode": 409,
                "body": json.dumps({
                    "error": "Artifact already exists",
                    "id": check_result[0]['id']
                })
            }
            log_response(response)  # <<< LOGGING
            return response

        # --------------------------
        # 4. RATING PIPELINE (only for models)
        # --------------------------
        url_handler = URLHandler()
        data_retriever = DataRetriever(
            github_token=os.environ.get("GITHUB_TOKEN"),
            hf_token=os.environ.get("HF_TOKEN")
        )

        model_obj: URLData = url_handler.handle_url(url)

        if not model_obj.is_valid:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "URL is not valid"})
            }
            log_response(response)  # <<< LOGGING
            return response

        if artifact_type == "model":
            if model_obj.category != URLCategory.HUGGINGFACE:
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Model must use a Hugging Face URL"})
                }
                log_response(response)  # <<< LOGGING
                return response
        elif artifact_type == "dataset":
            if model_obj.category not in (URLCategory.HUGGINGFACE, URLCategory.GITHUB, URLCategory.KAGGLE):
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Dataset must use a Hugging Face, GitHub, or Kaggle URL"})
                }
                log_response(response)  # <<< LOGGING
                return response
        elif artifact_type == "code":
            if model_obj.category != URLCategory.GITHUB:
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "URL is not a valid GitHub URL"})
                }
                log_response(response)  # <<< LOGGING
                return response

        repo_data = data_retriever.retrieve_data(model_obj)

        model_dict = {
            **repo_data.__dict__,
            "name": artifact_name
        }

        # Only calculate metrics for models
        if artifact_type == "model":
            calc = MetricCalculator()
            rating = calc.calculate_all_metrics(model_dict, category="MODEL")
            net_score = rating["net_score"]
        else:
            rating = {}
            net_score = None

        metadata_dict = repo_data.__dict__.copy()
        metadata_dict["requested_name"] = artifact_name
        if metadata_dict.get('created_at'):
            metadata_dict['created_at'] = metadata_dict['created_at'].isoformat()
        if metadata_dict.get('updated_at'):
            metadata_dict['updated_at'] = metadata_dict['updated_at'].isoformat()
        metadata_json = json.dumps(metadata_dict)

        # --------------------------
        # 6. Insert as upload_pending with download_url
        # --------------------------
        # First get the artifact_id, then construct download_url
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
                metadata_json
            ),
            fetch=True
        )

        artifact_id = result[0]['id']

        # Generate proper S3 HTTPS URL immediately
        download_url = f"https://{S3_BUCKET}.s3.us-east-1.amazonaws.com/{artifact_type}/{artifact_id}/"
        
        # Update the artifact with download_url
        run_query(
            """
            UPDATE artifacts
            SET download_url = %s
            WHERE id = %s;
            """,
            (download_url, artifact_id),
            fetch=False
        )

        # --------------------------
        # 6a. Auto-extract HF lineage from config.json (if present)
        # --------------------------

        auto_relationships = []

        # Load config.json (stringified JSON)
        raw_config = metadata_dict.get("config")
        try:
            config = json.loads(raw_config) if raw_config else {}
            print("[AUTOGRADER DEBUG] Parsed config JSON for artifact", config)
        except json.JSONDecodeError:
            config = {}
            print("[AUTOGRADER DEBUG] Failed to parse config JSON for artifact")

        # Helper: insert relationship into DB (if parent exists)
        def add_auto_rel(parent_name, relationship_type):
            if not parent_name or not isinstance(parent_name, str):
                return

            # Try to find parent artifact in DB by name
            parent_query = run_query(
                "SELECT id FROM artifacts WHERE name = %s;",
                (parent_name,),
                fetch=True
            )
            print(f"[AUTOGRADER DEBUG] add_auto_rel parent query:", parent_query)
            if parent_query and parent_query[0]:
                parent_id = parent_query[0]["id"]
                from_id = parent_id
                to_id = artifact_id

                # Insert into artifact_relationships table
                run_query(
                    """
                    INSERT INTO artifact_relationships
                    (from_artifact_id, to_artifact_id, relationship_type, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (from_id, to_id, relationship_type, "config_json"),
                    fetch=False
                )

                # Save into metadata for debugging / lineage lambda
                auto_relationships.append({
                    "artifact_id": parent_id,
                    "relationship": relationship_type,
                    "direction": "from"
                })

            else:
                # Parent isn't an artifact we know — save placeholder
                auto_relationships.append({
                    "artifact_id": parent_name,
                    "relationship": relationship_type,
                    "direction": "from",
                    "placeholder": True
                })

        # ---- RULE 1: PEFT / LoRA / Adapter ----
        if "base_model_name_or_path" in config:
            add_auto_rel(config["base_model_name_or_path"], "base_model")

        # ---- RULE 2: Fine-tuned / derived checkpoint ----
        # Note: Avoid self-referential loops
        if "_name_or_path" in config:
            val = config["_name_or_path"]
            if isinstance(val, str) and val != artifact_name:
                add_auto_rel(val, "derived_from")

        # ---- RULE 3: finetuned_from ----
        if "finetuned_from" in config:
            add_auto_rel(config["finetuned_from"], "fine_tuned_from")

        # ---- RULE 4: Distillation teacher ----
        if "teacher" in config:
            add_auto_rel(config["teacher"], "teacher_model")

        # ---- RULE 5: PEFT type (LoRA, prefix-tuning, etc.) ----
        if "peft_type" in config:
            base = config.get("base_model_name_or_path")
            peft_type = config["peft_type"].lower()
            if base:
                add_auto_rel(base, peft_type)

        # Save auto lineage entries into metadata
        if auto_relationships:
            metadata_dict["auto_lineage"] = auto_relationships

        # --------------------------
        # 6b. Create lineage relationship if provided
        # --------------------------
        if related_model_id and relationship_type:
            check_model = run_query(
                "SELECT id, type FROM artifacts WHERE id = %s;",
                (related_model_id,),
                fetch=True
            )
            
            if check_model:
                if artifact_type in ("dataset", "code"):
                    from_id = artifact_id
                    to_id = related_model_id
                elif artifact_type == "model":
                    from_id = related_model_id
                    to_id = artifact_id
                else:
                    from_id = artifact_id
                    to_id = related_model_id
                
                run_query(
                    """
                    INSERT INTO artifact_relationships (from_artifact_id, to_artifact_id, relationship_type, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (from_artifact_id, to_artifact_id, relationship_type) DO NOTHING;
                    """,
                    (from_id, to_id, relationship_type, "user_provided"),
                    fetch=False
                )

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
        response = {
            "statusCode": 201,
            "body": json.dumps({
                "metadata": {
                    "name": artifact_name,
                    "id": artifact_id,
                    "type": artifact_type
                },
                "data": {
                    "url": url,
                    "download_url": download_url
                }
            })
        }

        log_response(response)  # <<< LOGGING
        return response

    except Exception as e:
        log_exception(e)  # <<< LOGGING
        response = {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
        log_response(response)  # <<< LOGGING
        return response
