"""Twitter ETL Pipeline — Mock Data + MinIO (boto3).

Airflow DAG that:
1. Generates mock Twitter data (replaces Twitter API)
2. Cleans and flattens the data
3. Uploads to MinIO as Parquet + JSON via boto3
"""

import json
import logging
import os
from datetime import datetime
from io import BytesIO
from uuid import uuid4

from airflow.decorators import dag, task

logger = logging.getLogger(__name__)


@task
def generate_twitter_data():
    """Generate mock Twitter data (replaces Twitter API call)."""
    from mock_twitter_data import generate_mock_tweets

    tweets = generate_mock_tweets(count=20)
    logger.info("Generated %d mock tweets", len(tweets))
    return tweets


@task
def clean_twitter_data(tweets):
    """Clean and flatten tweet data for storage."""
    batch_id = uuid4().hex
    batch_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    tweet_list = []
    for tweet in tweets:
        refined = {
            "tweet_id": tweet["id"],
            "username": tweet["username"],
            "user_id": tweet["author_id"],
            "text": tweet["text"],
            "like_count": tweet["public_metrics"]["like_count"],
            "retweet_count": tweet["public_metrics"]["retweet_count"],
            "reply_count": tweet["public_metrics"]["reply_count"],
            "quote_count": tweet["public_metrics"]["quote_count"],
            "hashtags": ",".join(tweet.get("hashtags", [])),
            "lang": tweet["lang"],
            "created_at": tweet["created_at"],
            "batch_id": batch_id,
            "batch_datetime": batch_datetime,
        }
        tweet_list.append(refined)

    logger.info("Cleaned %d tweets, batch_id=%s", len(tweet_list), batch_id)
    return tweet_list, batch_datetime, batch_id


@task
def upload_to_minio(data):
    """Convert to Parquet + JSON and upload to MinIO via boto3."""
    import boto3
    import pandas as pd
    from botocore.client import Config

    tweet_list, batch_datetime_str, batch_id = data
    batch_dt = datetime.strptime(batch_datetime_str, "%Y-%m-%d %H:%M:%S")

    # Read MinIO config from environment
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    bucket = os.getenv("MINIO_BUCKET_NAME", "twitter-data")

    # Create boto3 S3 client for MinIO
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
        logger.info("Bucket '%s' exists", bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)
        logger.info("Created bucket '%s'", bucket)

    date_path = batch_dt.strftime("%Y/%m/%d")
    time_prefix = batch_dt.strftime("%H%M%S")

    # Upload Parquet
    df = pd.DataFrame(tweet_list)
    parquet_buffer = BytesIO()
    df.to_parquet(parquet_buffer, index=False)
    parquet_bytes = parquet_buffer.getvalue()

    parquet_key = f"tweets/{date_path}/tweets_{time_prefix}_{batch_id}.parquet"
    s3.put_object(
        Bucket=bucket,
        Key=parquet_key,
        Body=parquet_bytes,
        ContentType="application/octet-stream",
    )
    logger.info("Uploaded Parquet: %s (%d bytes)", parquet_key, len(parquet_bytes))

    # Upload JSON (raw data reference)
    json_bytes = json.dumps(tweet_list, indent=2, ensure_ascii=False).encode("utf-8")
    json_key = f"tweets/{date_path}/tweets_{time_prefix}_{batch_id}.json"
    s3.put_object(
        Bucket=bucket,
        Key=json_key,
        Body=json_bytes,
        ContentType="application/json",
    )
    logger.info("Uploaded JSON: %s (%d bytes)", json_key, len(json_bytes))


@dag(
    schedule="0 */6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["twitter", "etl", "mock-data"],
    doc_md="""
    ### Twitter ETL Pipeline (Mock Data)

    Generates mock Twitter data, cleans it, and uploads to MinIO as **Parquet + JSON**.

    - **Schedule**: Every 6 hours
    - **Storage**: MinIO bucket (S3-compatible)
    - **Format**: Parquet (for Drill queries) + JSON (raw backup)
    - **Upload**: via boto3
    """,
)
def twitter_etl():
    raw_data = generate_twitter_data()
    cleaned_data = clean_twitter_data(raw_data)
    upload_to_minio(cleaned_data)


twitter_etl()
