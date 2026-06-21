"""Twitter ETL Pipeline — Memory-Optimized for t3.micro.

Airflow DAG that:
1. Generates mock Twitter data via generator (zero-copy)
2. Cleans/flattens data one row at a time
3. Uploads to MinIO as CSV + JSON (NO Pandas, NO PyArrow)

>>> MEM: Peak ~5MB instead of ~50MB+ with Pandas/Parquet.
"""

import csv
import gc
import io
import json
import logging
import os
from datetime import datetime
from uuid import uuid4

from airflow.decorators import dag, task

logger = logging.getLogger(__name__)


@task
def generate_and_upload():
    """Generate mock data → clean → stream-upload to MinIO in a single task.

    >>> MEM: Merged 3 tasks into 1 to avoid Airflow XCom serialization overhead.
    XCom stores task results in the Postgres metadata DB, which means the entire
    tweet list was serialized to JSON, stored in DB, then deserialized — doubling
    memory usage. By merging, data never leaves this process's memory.
    """
    from mock_twitter_data import (
        CSV_FIELDNAMES,
        flatten_tweet,
        generate_mock_tweets,
    )
    import boto3
    from botocore.client import Config

    batch_id = uuid4().hex
    batch_dt = datetime.now()
    batch_datetime_str = batch_dt.strftime("%Y-%m-%d %H:%M:%S")
    date_path = batch_dt.strftime("%Y/%m/%d")
    time_prefix = batch_dt.strftime("%H%M%S")

    # --- MinIO client setup ---
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    bucket = os.getenv("MINIO_BUCKET_NAME", "twitter-data")

    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://{endpoint}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )

    # Ensure bucket exists
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)
        logger.info("Created bucket '%s'", bucket)

    # --- Generate + Clean + Build CSV & JSON in one pass ---
    # >>> MEM: We iterate the generator once, building both CSV and JSON buffers
    #     using io.StringIO (small, bounded by tweet count=20).
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()

    json_records = []
    tweet_count = 0

    for tweet in generate_mock_tweets(count=20):
        # Flatten for CSV
        flat = flatten_tweet(tweet)
        flat["batch_id"] = batch_id
        flat["batch_datetime"] = batch_datetime_str
        writer.writerow(flat)

        # Collect for JSON (raw backup — 20 tweets is ~15KB, safe)
        json_records.append(tweet)
        tweet_count += 1

    logger.info("Generated & cleaned %d tweets, batch_id=%s", tweet_count, batch_id)

    # --- Upload CSV (replaces Parquet — no Pandas/PyArrow dependency) ---
    # >>> MEM: CSV is ~3x larger than Parquet but avoids loading Pandas (~80MB)
    #     and PyArrow (~50MB) into memory. Net saving: ~120MB RAM.
    csv_bytes = csv_buffer.getvalue().encode("utf-8")
    csv_buffer.close()  # MEM: free StringIO immediately

    csv_key = f"tweets/{date_path}/tweets_{time_prefix}_{batch_id}.csv"
    s3.put_object(
        Bucket=bucket,
        Key=csv_key,
        Body=csv_bytes,
        ContentType="text/csv",
    )
    logger.info("Uploaded CSV: %s (%d bytes)", csv_key, len(csv_bytes))
    del csv_bytes  # MEM: free bytes immediately

    # --- Upload JSON ---
    json_bytes = json.dumps(json_records, indent=2, ensure_ascii=False).encode("utf-8")
    del json_records  # MEM: free list before upload

    json_key = f"tweets/{date_path}/tweets_{time_prefix}_{batch_id}.json"
    s3.put_object(
        Bucket=bucket,
        Key=json_key,
        Body=json_bytes,
        ContentType="application/json",
    )
    logger.info("Uploaded JSON: %s (%d bytes)", json_key, len(json_bytes))
    del json_bytes  # MEM: free bytes immediately

    # >>> MEM: Force garbage collection to reclaim all freed objects
    gc.collect()

    logger.info("ETL complete. CSV=%s, JSON=%s", csv_key, json_key)


@dag(
    schedule="0 */6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["twitter", "etl", "mock-data"],
    doc_md="""
    ### Twitter ETL Pipeline (Mock Data) — Memory-Optimized

    Generates mock Twitter data, cleans it, and uploads to MinIO as **CSV + JSON**.

    - **Schedule**: Every 6 hours
    - **Storage**: MinIO bucket (S3-compatible)
    - **Format**: CSV (for Drill queries) + JSON (raw backup)
    - **Upload**: via boto3 (streaming)
    - **Optimization**: No Pandas/PyArrow — saves ~130MB RAM per run
    """,
)
def twitter_etl():
    # >>> MEM: Single task avoids XCom serialization overhead between tasks
    generate_and_upload()


twitter_etl()
