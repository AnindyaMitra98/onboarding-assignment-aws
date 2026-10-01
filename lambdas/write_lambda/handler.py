"""write-lambda: consumes JSON events from SQS and saves each one as a file in S3.

Environment variables:
    BUCKET_NAME    - S3 bucket the JSON files are written to
    OUTPUT_PREFIX  - optional key prefix for written files, defaults to "output/"
    LOG_LEVEL      - optional, defaults to INFO
"""

import json
import logging
import os
import posixpath

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

BUCKET_NAME = os.environ["BUCKET_NAME"]
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "output/")

s3 = boto3.client("s3")


def lambda_handler(event, context):
    records = event.get("Records", [])
    logger.info("Received %d SQS message(s)", len(records))

    # Report failures per message so one bad event doesn't re-drive the whole batch.
    failures = []
    for record in records:
        message_id = record["messageId"]
        try:
            key = save_event(record)
            logger.info("Saved message %s to s3://%s/%s", message_id, BUCKET_NAME, key)
        except Exception:
            logger.exception("Failed to save message %s", message_id)
            failures.append({"itemIdentifier": message_id})

    logger.info("Saved %d of %d message(s)", len(records) - len(failures), len(records))
    return {"batchItemFailures": failures}


def save_event(record):
    # Validate the payload is JSON before writing it.
    payload = json.loads(record["body"])
    key = object_key(record)

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )
    return key


def object_key(record):
    """Derive a deterministic key so retried messages overwrite instead of duplicating.

    Uses the source file and line number forwarded by read-lambda as message
    attributes, e.g. input/people.csv line 7 -> output/people/000007.json.
    Falls back to the SQS message id when those attributes are missing.
    """
    attributes = record.get("messageAttributes", {})
    source_key = attributes.get("source_key", {}).get("stringValue")
    line_number = attributes.get("line_number", {}).get("stringValue")

    if source_key and line_number:
        source_name = posixpath.splitext(posixpath.basename(source_key))[0]
        return f"{OUTPUT_PREFIX}{source_name}/{int(line_number):06d}.json"

    return f"{OUTPUT_PREFIX}{record['messageId']}.json"
