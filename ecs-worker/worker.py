import os
import json
import boto3
import psycopg2
import urllib.request
import zipfile
import tempfile
from urllib.parse import urlparse

# -------------------
# AWS CLIENTS
# -------------------
sqs = boto3.client("sqs")
s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager")

QUEUE_URL = os.environ["QUEUE_URL"]
S3_BUCKET = os.environ["S3_BUCKET"]
SECRET_NAME = os.environ["SECRET_NAME"]
HF_TOKEN = os.environ.get("HF_TOKEN")  # Optional but avoids HF rate limits

# -------------------
# DB CONNECTION SETUP
# -------------------


def get_db_connection():
    secret = secrets.get_secret_value(SecretId=SECRET_NAME)
    creds = json.loads(secret["SecretString"])

    return psycopg2.connect(
        host=creds["DB_HOST"],
        port=creds["DB_PORT"],
        dbname=creds["DB_NAME"],
        user=creds["DB_USER"],
        password=creds["DB_PASS"],
    )

# -------------------
# HELPERS
# -------------------


def parse_hf_identifier(url: str):
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    # Handle /datasets/name, /spaces/name, or /owner/model patterns
    if len(parts) >= 2:
        if parts[0] in ['datasets', 'spaces']:
            # /datasets/name or /datasets/owner/name
            if len(parts) >= 3:
                return f"{parts[1]}/{parts[2]}"
            else:
                return parts[1]
        else:
            # /owner/model
            return f"{parts[0]}/{parts[1]}"
    elif len(parts) == 1:
        # Single-part path like /model-name
        return parts[0]
    return None


def list_hf_files(identifier: str):
    api_url = f"https://huggingface.co/api/models/{identifier}"
    req = urllib.request.Request(api_url)
    req.add_header("User-Agent", "ECE461-Model-Ingest-Worker")

    if HF_TOKEN:
        req.add_header("Authorization", f"Bearer {HF_TOKEN}")

    with urllib.request.urlopen(req) as response:
        data = json.load(response)
        siblings = data.get("siblings", [])
        return [file["rfilename"] for file in siblings]


def stream_file_to_s3(url, bucket, key):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "ECE461-Model-Ingest-Worker")

    if HF_TOKEN:
        req.add_header("Authorization", f"Bearer {HF_TOKEN}")

    with urllib.request.urlopen(req) as response:
        s3.upload_fileobj(response, bucket, key)


# -------------------
# WORKER MAIN LOOP
# -------------------
print("Worker started. Waiting for messages...")

while True:
    resp = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20
    )

    if "Messages" not in resp:
        continue

    msg = resp["Messages"][0]
    receipt = msg["ReceiptHandle"]

    raw_body = msg.get("Body", "")
    try:
        body = json.loads(raw_body)
        # Some producers may double-encode or send plain IDs; normalize to dicts only.
        if isinstance(body, str):
            body = json.loads(body)
    except Exception:
        print(f"Error decoding message body; skipping. body={raw_body}")
        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt)
        continue

    if not isinstance(body, dict):
        print(f"Unexpected message body type {type(body)}; skipping. body={body}")
        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt)
        continue

    artifact_id = body["artifact_id"]
    artifact_type = body["artifact_type"]
    url = body["source_url"]

    try:
        workdir = tempfile.mkdtemp(prefix=f"artifact_{artifact_id}_")
        identifier = parse_hf_identifier(url)
        files = list_hf_files(identifier)

        # Download each file from HF → upload to S3
        # for filename in files:
        #     hf_url = f"https://huggingface.co/{identifier}/resolve/main/{filename}"
        #     s3_key = f"{artifact_type}/{artifact_id}/{filename}"

        #     print(f"Uploading {filename} → s3://{S3_BUCKET}/{s3_key}")
        #     stream_file_to_s3(hf_url, S3_BUCKET, s3_key)

        local_files = []

        for filename in files:
            hf_url = f"https://huggingface.co/{identifier}/resolve/main/{filename}"
            local_path = os.path.join(workdir, filename)

            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            print(f"Downloading {filename} → {local_path}")

            req = urllib.request.Request(hf_url)
            req.add_header("User-Agent", "ECE461-Model-Ingest-Worker")

            if HF_TOKEN:
                req.add_header("Authorization", f"Bearer {HF_TOKEN}")

            with urllib.request.urlopen(req) as response, open(local_path, "wb") as f:
                f.write(response.read())

            local_files.append(local_path)

        zip_path = os.path.join(workdir, "artifact.zip")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in local_files:
                arcname = os.path.relpath(file_path, workdir)
                zipf.write(file_path, arcname)

        print(f"Created ZIP: {zip_path}")
        
        zip_s3_key = f"{artifact_type}/{artifact_id}/artifact.zip"

        print(f"Uploading ZIP → s3://{S3_BUCKET}/{zip_s3_key}")

        s3.upload_file(
            zip_path,
            S3_BUCKET,
            zip_s3_key,
            ExtraArgs={
                "ContentType": "application/zip",
                "ContentDisposition": f'attachment; filename="{artifact_id}.zip"'
            }
        )
        
        for file_path in local_files:
            key = f"{artifact_type}/{artifact_id}/{os.path.relpath(file_path, workdir)}"
            s3.upload_file(file_path, S3_BUCKET, key)

        print("Download completed.")

        # ----------------------------------
        # UPDATE DATABASE → make artifact available
        # ----------------------------------
        conn = get_db_connection()
        cur = conn.cursor()

        # Generate proper S3 HTTPS URL (region-specific)
        # Format: https://<bucket>.s3.<region>.amazonaws.com/<key>
        # s3_https_url = f"https://{S3_BUCKET}.s3.us-east-1.amazonaws.com/{artifact_type}/{artifact_id}/"
        # download_url = %s
        cur.execute("""
                UPDATE artifacts
                SET status = 'available'
                WHERE id = %s;
            """, (artifact_id,))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("Error during ingestion:", e)

    # Remove message from queue
    sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt)
