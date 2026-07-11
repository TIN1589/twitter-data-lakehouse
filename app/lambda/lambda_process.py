import os
import json
import logging
from datetime import datetime
from io import BytesIO
import boto3
import pandas as pd

from models import CleanedTweet
from data_quality import DataQualityChecker

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """AWS Lambda handler for the transformation/processing stage.
    
    1. Reads raw JSON data from S3.
    2. Cleans and flattens nested fields.
    3. Validates against CleanedTweet schema.
    4. Converts to Parquet with Snappy compression.
    5. Saves to partitioned processed directory on S3.
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract details from ingest output
    bucket_name = event["bucket"]
    raw_key = event["raw_key"]
    batch_id = event["batch_id"]
    batch_datetime = event["batch_datetime"]
    
    s3 = boto3.client("s3")
    
    # 1. Read raw JSON from S3
    logger.info(f"Reading raw JSON from S3: s3://{bucket_name}/{raw_key}")
    response = s3.get_object(Bucket=bucket_name, Key=raw_key)
    raw_tweets = json.loads(response["Body"].read().decode("utf-8"))
    logger.info(f"Successfully loaded {len(raw_tweets)} tweets")
    
    # 2. Process and Clean
    tweet_list = []
    for tweet in raw_tweets:
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
        
    # 3. Validate cleaned structure
    checker = DataQualityChecker(batch_id)
    cleaned_tweets_validated, clean_validation_result = checker.validate_cleaned_tweets(tweet_list)
    
    if not cleaned_tweets_validated:
        raise ValueError("Cleaned tweet validation failed")
        
    # 4. Convert to Parquet using Pandas
    logger.info("Converting to Parquet format...")
    df = pd.DataFrame(cleaned_tweets_validated)
    parquet_buffer = BytesIO()
    
    # Save to buffer using snappy compression
    df.to_parquet(parquet_buffer, index=False, compression="snappy")
    parquet_bytes = parquet_buffer.getvalue()
    
    # 5. Save to partitioned processed directory: processed/year=YYYY/month=MM/day=DD/
    batch_dt = datetime.strptime(batch_datetime, "%Y-%m-%d %H:%M:%S")
    date_path = batch_dt.strftime("year=%Y/month=%m/day=%d")
    time_prefix = batch_dt.strftime("%H%M%S")
    
    parquet_key = f"processed/{date_path}/tweets_{time_prefix}_{batch_id}.parquet"
    
    logger.info(f"Uploading Parquet to S3: s3://{bucket_name}/{parquet_key}")
    s3.put_object(
        Bucket=bucket_name,
        Key=parquet_key,
        Body=parquet_bytes,
        ContentType="application/octet-stream"
    )
    logger.info("Successfully uploaded Parquet to S3")
    
    return {
        "status": "success",
        "bucket": bucket_name,
        "parquet_key": parquet_key,
        "batch_id": batch_id,
        "batch_datetime": batch_datetime,
        "tweets_count": len(cleaned_tweets_validated)
    }
