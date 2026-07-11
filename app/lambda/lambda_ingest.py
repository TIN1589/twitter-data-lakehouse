import os
import json
import logging
from datetime import datetime
from uuid import uuid4
import boto3

from mock_twitter_data import generate_mock_tweets
from models import RawTweet
from data_quality import DataQualityChecker, quality_check_report_to_dict

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """AWS Lambda handler for the ingestion stage.
    
    1. Generates mock Twitter data (or reads API).
    2. Validates data quality using Pydantic models.
    3. Saves raw JSON data to S3.
    """
    logger.info("Starting Twitter Data Ingestion...")
    
    # 1. Read configuration from environment
    bucket_name = os.getenv("S3_BUCKET_NAME", "prod-twitter-data-lakehouse")
    min_valid_rate = float(os.getenv("MIN_VALID_TWEET_RATE", "0.8"))
    
    # Initialize S3 client (inherits credentials from IAM Role)
    s3 = boto3.client("s3")
    
    # 2. Generate data (20 tweets)
    tweets = generate_mock_tweets(count=20)
    logger.info(f"Generated {len(tweets)} tweets")
    
    # 3. Validate data
    batch_id = uuid4().hex
    checker = DataQualityChecker(batch_id)
    valid_tweets, quality_result = checker.validate_raw_tweets(tweets)
    
    report_dict = quality_check_report_to_dict(quality_result)
    logger.info(f"Quality check results: {json.dumps(report_dict)}")
    
    # Check valid rate
    valid_rate = len(valid_tweets) / len(tweets) if tweets else 0
    if valid_rate < min_valid_rate:
        raise ValueError(
            f"Data quality validation failed: {valid_rate:.1%} valid tweets < "
            f"required {min_valid_rate:.1%}"
        )
        
    # 4. Save raw JSON to S3
    batch_dt = datetime.utcnow()
    date_path = batch_dt.strftime("year=%Y/month=%m/day=%d")
    time_prefix = batch_dt.strftime("%H%M%S")
    batch_datetime = batch_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    raw_key = f"raw/{date_path}/tweets_{time_prefix}_{batch_id}.json"
    
    json_bytes = json.dumps(valid_tweets, indent=2, ensure_ascii=False).encode("utf-8")
    s3.put_object(
        Bucket=bucket_name,
        Key=raw_key,
        Body=json_bytes,
        ContentType="application/json"
    )
    logger.info(f"Successfully uploaded raw JSON to S3: s3://{bucket_name}/{raw_key}")
    
    # Return output for the next Step Function state
    return {
        "status": "success",
        "bucket": bucket_name,
        "raw_key": raw_key,
        "batch_id": batch_id,
        "batch_datetime": batch_datetime,
        "tweets_count": len(valid_tweets)
    }
