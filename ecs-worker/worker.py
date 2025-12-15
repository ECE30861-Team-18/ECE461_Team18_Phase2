import os
import json
import boto3
import psycopg2
import urllib.request
from urllib.parse import urlparse
import zipstream

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
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

ZIP_PART_SIZE = 8 * 1024 * 1024  # 8MB multipart part size
STREAM_CHUNK_SIZE = 1024 * 1024  # 1MB read chunks

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


def list_artifact_objects(bucket: str, prefix: str):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            yield item["Key"]


def stream_zip_from_s3_to_s3(bucket: str, prefix: str, zip_key: str):
    # Create streaming zip
    z = zipstream.ZipStream(compress_type=zipstream.ZIP_DEFLATED)

    def make_generator(key: str):
        obj = s3.get_object(Bucket=bucket, Key=key)
        for chunk in obj["Body"].iter_chunks(chunk_size=STREAM_CHUNK_SIZE):
            if chunk:
                yield chunk

    # Add each S3 object to the streaming zip using a generator source
    for key in list_artifact_objects(bucket, prefix):
        arcname = key[len(prefix):] if key.startswith(prefix) else key
        z.add(make_generator(key), arcname)

    # Multipart upload for the zip output
    upload = s3.create_multipart_upload(
        Bucket=bucket,
        Key=zip_key,
        ContentType="application/zip",
        ContentDisposition=f'attachment; filename="{os.path.basename(zip_key)}"',
    )

    parts = []
    part_number = 1
    buffer = b""

    try:
        for chunk in z:
            if not chunk:
                continue
            buffer += chunk
            while len(buffer) >= ZIP_PART_SIZE:
                part_data, buffer = buffer[:ZIP_PART_SIZE], buffer[ZIP_PART_SIZE:]
                resp = s3.upload_part(
                    Bucket=bucket,
                    Key=zip_key,
                    UploadId=upload["UploadId"],
                    PartNumber=part_number,
                    Body=part_data,
                )
                parts.append({"ETag": resp["ETag"], "PartNumber": part_number})
                part_number += 1

        # Final part
        if buffer:
            resp = s3.upload_part(
                Bucket=bucket,
                Key=zip_key,
                UploadId=upload["UploadId"],
                PartNumber=part_number,
                Body=buffer,
            )
            parts.append({"ETag": resp["ETag"], "PartNumber": part_number})

        s3.complete_multipart_upload(
            Bucket=bucket,
            Key=zip_key,
            UploadId=upload["UploadId"],
            MultipartUpload={"Parts": parts},
        )
    except Exception:
        s3.abort_multipart_upload(
            Bucket=bucket,
            Key=zip_key,
            UploadId=upload["UploadId"],
        )
        raise


# -------------------
# WORKER MAIN LOOP
# -------------------
print("Worker started.  Waiting for messages...")

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
    body = json.loads(msg["Body"])

    artifact_id = body["artifact_id"]
    artifact_type = body["artifact_type"]
    url = body["source_url"]

    try:
        identifier = parse_hf_identifier(url)
        files = list_hf_files(identifier)

        # Download each file from HF → upload to S3
        for filename in files:
            hf_url = f"https://huggingface.co/{identifier}/resolve/main/{filename}"
            s3_key = f"{artifact_type}/{artifact_id}/{filename}"

            print(f"Uploading {filename} → s3://{S3_BUCKET}/{s3_key}")
            stream_file_to_s3(hf_url, S3_BUCKET, s3_key)

        print("Download completed.")

        # Build ZIP directly from S3 objects back to S3 (no local disk)
        zip_s3_key = f"{artifact_type}/{artifact_id}/artifact.zip"
        print(f"Creating ZIP → s3://{S3_BUCKET}/{zip_s3_key}")
        stream_zip_from_s3_to_s3(
            bucket=S3_BUCKET,
            prefix=f"{artifact_type}/{artifact_id}/",
            zip_key=zip_s3_key,
        )

        # ----------------------------------
        # UPDATE DATABASE → make artifact available
        # ----------------------------------
        conn = get_db_connection()
        cur = conn.cursor()

        # Generate proper S3 HTTPS URL (region-specific) for the ZIP
        s3_https_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{zip_s3_key}"

        cur.execute("""
            UPDATE artifacts
            SET status = 'available',
                download_url = %s
            WHERE id = %s;
        """, (s3_https_url, artifact_id))

        conn.commit()
        cur.close()
        conn.close()

        print(f"DB updated: artifact {artifact_id} is now AVAILABLE at {s3_https_url}.")

    except Exception as e:
        print("Error during ingestion:", e)

    # Remove message from queue
    sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt)