"""read-lambda: triggered by S3, converts each CSV line to JSON and publishes it to SNS.

Environment variables:
    BUCKET_NAME    - S3 bucket holding the input CSV files
    SNS_TOPIC_ARN  - topic every JSON event is published to
    LOG_LEVEL      - optional, defaults to INFO
"""

import codecs
import csv
import json
import logging
import os
from urllib.parse import unquote_plus

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

BUCKET_NAME = os.environ["BUCKET_NAME"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

# SNS PublishBatch accepts at most 10 entries per call.
SNS_BATCH_SIZE = 10

s3 = boto3.client("s3")
sns = boto3.client("sns")


def lambda_handler(event, context):
    records = event.get("Records", [])
    logger.info("Received S3 event with %d record(s)", len(records))

    results = []
    for record in records:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        if bucket != BUCKET_NAME:
            logger.warning("Skipping object from unexpected bucket %s", bucket)
            continue

        published = process_csv(bucket, key)
        results.append({"key": key, "published": published})

    logger.info("Finished processing: %s", results)
    return {"processed": results}


def process_csv(bucket, key):
    """Stream the CSV from S3 and publish one SNS message per data line."""
    logger.info("Reading s3://%s/%s", bucket, key)
    body = s3.get_object(Bucket=bucket, Key=key)["Body"]

    # utf-8-sig drops the BOM that spreadsheet exports often prepend.
    reader = csv.DictReader(codecs.getreader("utf-8-sig")(body))

    batch = []
    published = 0
    for line_number, row in enumerate(reader, start=2):  # line 1 is the header
        batch.append(build_entry(key, line_number, row))
        if len(batch) == SNS_BATCH_SIZE:
            published += publish_batch(batch)
            batch = []
    if batch:
        published += publish_batch(batch)

    logger.info("Published %d event(s) from s3://%s/%s", published, bucket, key)
    return published


def build_entry(source_key, line_number, row):
    # A row with more values than headers stores the extras under the None key,
    # which json.dumps would turn into "null"; give it a readable name instead.
    if None in row:
        row["_extra"] = row.pop(None)

    return {
        "Id": str(line_number),
        "Message": json.dumps(row),
        "MessageAttributes": {
            "source_key": {"DataType": "String", "StringValue": source_key},
            "line_number": {"DataType": "Number", "StringValue": str(line_number)},
        },
    }


def publish_batch(entries):
    response = sns.publish_batch(TopicArn=SNS_TOPIC_ARN, PublishBatchRequestEntries=entries)

    failed = response.get("Failed", [])
    if failed:
        logger.error("Failed to publish %d event(s): %s", len(failed), failed)
        # Fail the invocation so S3's async retry re-processes the file.
        raise RuntimeError(f"SNS publish failed for {len(failed)} event(s)")

    logger.debug("Published batch of %d event(s)", len(entries))
    return len(entries)
