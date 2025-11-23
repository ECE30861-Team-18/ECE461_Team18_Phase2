import os
import json
import time
import logging
from typing import Optional, Dict, Any, List

import boto3
import psycopg2
import requests

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------- Environment ----------
S3_BUCKET = os.environ.get("S3_BUCKET")
SECRET_NAME = os.environ.get("SECRET_NAME", "DB_CREDS")
QUEUE_URL = os.environ.get("QUEUE_URL")  # same name as in Lambda
HF_TOKEN = os.environ.get("HF_TOKEN")

if not S3_BUCKET or not SECRET_NAME or not QUEUE_URL:
    logger.error("Missing required environment vars: S3_BUCKET, SECRET_NAME, INGEST_QUEUE_URL")
    raise SystemExit(1)

# ---------- AWS Clients ----------
s3_client = boto3.client("s3")
sqs_client = boto3.client("sqs")
secrets_client = boto3.client("secretsmanager")


# ---------- DB Helper ----------
def get_db_connection():
    """Get Postgres connection using Secrets Manager."""
    secret_response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
    creds = json.loads(secret_response["SecretString"])

    conn = psycopg2.connect(
        host=creds["DB_HOST"],
        port=creds.get("DB_PORT", "5432"),
        dbname=creds["DB_NAME"],
        user=creds["DB_USER"],
        password=creds["DB_PASS"],
        connect_timeout=5,
    )
    conn.autocommit = True
    return conn


# ---------- Hugging Face helpers ----------
def get_hf_headers() -> Dict[str, str]:
    headers = {"User-Agent": "ECE461-Model-Ingest-Worker"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    return headers


def list_hf_files(identifier: str) -> List[str]:
    """
    Call Hugging Face API to list model files.
    Returns list of rfilename strings.
    """
    api_url = f"https://huggingface.co/api/models/{identifier}"
    logger.info("Fetching HF model metadata for %s", identifier)

    resp = requests.get(api_url, headers=get_hf_headers(), timeout=60)
    if resp.status_code == 404:
        raise RuntimeError(f"Model not found on Hugging Face: {identifier}")
    resp.raise_for_status()

    data = resp.json()
    siblings = data.get("siblings", [])
    files = [s["rfilename"] for s in siblings if "rfilename" in s]
    logger.info("Model %s has %d files", identifier, len(files))
    return files


def upload_file_to_s3_from_hf(identifier: str, artifact_type: str, artifact_id: int, filename: str):
    """
    Stream a single file from HF → S3 using streaming download.
    """
    hf_url = f"https://huggingface.co/{identifier}/resolve/main/{filename}"
    s3_key = f"{artifact_type}/{artifact_id}/{filename}"

    logger.info("Streaming %s -> s3://%s/%s", hf_url, S3_BUCKET, s3_key)

    with requests.get(hf_url, headers=get_hf_headers(), stream=True, timeout=600) as r:
        r.raise_for_status()
        # Stream directly to S3 without buffering whole file in memory
        s3_client.upload_fileobj(r.raw, S3_BUCKET, s3_key)


# ---------- DB status update ----------
def update_artifact_status(artifact_id: int, new_status: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE artifacts SET status = %s WHERE id = %s;",
                (new_status, artifact_id),
            )
        logger.info("Updated artifact %s status -> %s", artifact_id, new_status)
    finally:
        conn.close()


# ---------- Message Processing ----------
def process_ingest_message(msg_body: str):
    """
    msg_body is JSON from SQS:
    {
      "artifact_id": int,
      "artifact_type": "model" | "dataset" | "code",
      "identifier": "owner/name",
      "source_url": "https://huggingface.co/owner/name"
    }
    """
    data = json.loads(msg_body)
    artifact_id = int(data["artifact_id"])
    artifact_type = data["artifact_type"]
    identifier = data["identifier"]

    logger.info("Processing ingest for artifact_id=%s, identifier=%s", artifact_id, identifier)

    # Make sure DB row is marked upload_pending
    update_artifact_status(artifact_id, "upload_pending")

    files = list_hf_files(identifier)
    if not files:
        logger.warning("No files found for HF model %s", identifier)

    for filename in files:
        try:
            upload_file_to_s3_from_hf(identifier, artifact_type, artifact_id, filename)
        except Exception as e:
            logger.error("Failed uploading %s for artifact %s: %s", filename, artifact_id, e)
            # You can decide whether to fail whole job or continue.
            # For now, we fail hard so the message stays in SQS for retry.
            raise

    # Mark available if all files succeeded
    update_artifact_status(artifact_id, "available")
    logger.info("Ingest complete for artifact_id=%s", artifact_id)


# ---------- Main loop ----------
def main_loop():
    logger.info("Starting ingest worker, queue=%s", QUEUE_URL)

    while True:
        try:
            resp = sqs_client.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,      # long polling
                VisibilityTimeout=600,   # time for ingest
            )

            messages = resp.get("Messages", [])
            if not messages:
                # idle
                continue

            for msg in messages:
                receipt_handle = msg["ReceiptHandle"]
                body = msg["Body"]

                try:
                    process_ingest_message(body)
                    # Success -> delete message
                    sqs_client.delete_message(
                        QueueUrl=QUEUE_URL,
                        ReceiptHandle=receipt_handle,
                    )
                    logger.info("Deleted SQS message after successful ingest")
                except Exception as e:
                    logger.exception("Error processing message, leaving in queue for retry: %s", e)
                    # DO NOT delete message so it can be retried after visibility timeout
                    # Maybe sleep a bit to avoid tight error loops
                    time.sleep(5)

        except Exception as outer_e:
            logger.exception("Outer loop error: %s", outer_e)
            time.sleep(5)  # avoid spinning like crazy on repeated failure


if __name__ == "__main__":
    main_loop()
