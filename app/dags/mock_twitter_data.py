"""Mock Twitter Data Generator — Memory-Optimized.

Generates fake tweet data using Python generators (yield).
NO Pandas, NO large in-memory lists. Data is streamed chunk-by-chunk.
Optimized for AWS EC2 t3.micro (1GB RAM + 4GB Swap).
"""

import csv
import gc
import io
import json
import os
import random
from datetime import datetime, timedelta

# Realistic sample tweets (tech/business themed)
SAMPLE_TEXTS = [
    "Just had an incredible meeting about the future of AI. The possibilities are truly endless! 🚀",
    "SpaceX Starship test flight was amazing today. One step closer to Mars! 🌟",
    "Tesla just broke another delivery record this quarter. Proud of the entire team! ⚡",
    "The future of sustainable energy is here. Solar + batteries will change everything.",
    "Working on something exciting at the Gigafactory. Can't wait to share more soon!",
    "Free speech is the bedrock of a functioning democracy.",
    "Autopilot is getting better every day. Neural net improvements are remarkable.",
    "Starlink now has over 2 million active subscribers worldwide 🛰️",
    "Just visited the Boring Company tunnel. Transportation will never be the same.",
    "AI safety is one of the most important issues of our time. We need to get this right.",
    "Production at record levels. The team is executing incredibly well.",
    "Innovation happens when you push boundaries and refuse to accept the status quo.",
    "Mars is looking more achievable every day. Humanity's future is multiplanetary.",
    "Battery technology is the key to solving climate change. We're making progress.",
    "Engineering is the closest thing to magic that exists in this world.",
    "Just reviewed the latest FSD beta. The improvement curve is exponential.",
    "Space exploration inspires the next generation of scientists and engineers.",
    "Building the machine that builds the machine. That's the real challenge.",
    "Renewable energy adoption is accelerating faster than anyone predicted.",
    "The best part of my job is working with incredibly talented people every day.",
    "Neural networks are getting smarter. The implications are profound.",
    "Every great company was once a startup with a crazy idea.",
    "Open source AI will democratize technology for everyone on the planet.",
    "Rocket landing success rate keeps improving. Reusability is the future of space.",
    "Electric vehicles are not just better for the environment, they're better cars. Period.",
]

SAMPLE_HASHTAGS_POOL = [
    ["AI", "FutureTech"],
    ["SpaceX", "Mars", "Space"],
    ["Tesla", "EV", "ElectricVehicles"],
    ["Energy", "Solar", "Sustainability"],
    ["Innovation", "Tech"],
    ["Starlink", "Internet", "Satellite"],
    ["Engineering", "Science"],
    ["FSD", "Autopilot", "SelfDriving"],
    ["ClimateChange", "CleanEnergy"],
    ["OpenSource", "AI"],
]

# --- CSV column definition (single source of truth) ---
CSV_FIELDNAMES = [
    "id", "text", "created_at", "author_id", "username",
    "lang", "like_count", "retweet_count", "reply_count",
    "quote_count", "hashtags", "batch_id", "batch_datetime",
]


def generate_mock_tweets(count=20):
    """Generator: yields one mock tweet dict at a time.

    >>> MEM: O(1) per tweet instead of O(N) for entire list.
    """
    base_time = datetime.utcnow()

    for _ in range(count):
        created_at = base_time - timedelta(
            minutes=random.randint(1, 1440),
            seconds=random.randint(0, 59),
        )
        yield {
            "id": str(random.randint(10**17, 10**18 - 1)),
            "text": random.choice(SAMPLE_TEXTS),
            "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "author_id": "44196397",
            "username": "elonmusk",
            "lang": random.choice(["en", "en", "en", "es", "fr"]),
            "public_metrics": {
                "like_count": random.randint(500, 800000),
                "retweet_count": random.randint(100, 200000),
                "reply_count": random.randint(50, 80000),
                "quote_count": random.randint(10, 30000),
            },
            "hashtags": random.choice(SAMPLE_HASHTAGS_POOL),
        }


def flatten_tweet(tweet):
    """Flatten a single tweet dict for CSV/tabular storage.

    >>> MEM: processes one tweet at a time, no intermediate list.
    """
    return {
        "id": tweet["id"],
        "text": tweet["text"],
        "created_at": tweet["created_at"],
        "author_id": tweet["author_id"],
        "username": tweet["username"],
        "lang": tweet["lang"],
        "like_count": tweet["public_metrics"]["like_count"],
        "retweet_count": tweet["public_metrics"]["retweet_count"],
        "reply_count": tweet["public_metrics"]["reply_count"],
        "quote_count": tweet["public_metrics"]["quote_count"],
        "hashtags": ",".join(tweet.get("hashtags", [])),
    }


def save_to_json_streaming(tweets_gen, filepath):
    """Stream-write tweets as JSON array, one tweet at a time.

    >>> MEM: only 1 tweet in memory at any moment.
    """
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("[\n")
        first = True
        for tweet in tweets_gen:
            if not first:
                f.write(",\n")
            json.dump(tweet, f, ensure_ascii=False)
            first = False
        f.write("\n]")


def save_to_csv_streaming(tweets_gen, filepath):
    """Stream-write flattened tweets as CSV, one row at a time.

    >>> MEM: only 1 flattened tweet in memory at any moment.
    """
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for tweet in tweets_gen:
            writer.writerow(flatten_tweet(tweet))


def get_s3_client():
    """Create a boto3 S3 client for MinIO (shared helper)."""
    import boto3
    from botocore.client import Config

    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

    return boto3.client(
        "s3",
        endpoint_url=f"http://{endpoint}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket(s3, bucket_name):
    """Create bucket if it doesn't exist."""
    try:
        s3.head_bucket(Bucket=bucket_name)
    except Exception:
        s3.create_bucket(Bucket=bucket_name)


def upload_to_minio_stream(file_obj, bucket_name, object_key, content_type="application/octet-stream"):
    """Upload a file-like object to MinIO using streaming multipart upload.

    >>> MEM: uses upload_fileobj (multipart) instead of put_object (full bytes in RAM).
    """
    s3 = get_s3_client()
    ensure_bucket(s3, bucket_name)

    s3.upload_fileobj(
        Fileobj=file_obj,
        Bucket=bucket_name,
        Key=object_key,
        ExtraArgs={"ContentType": content_type},
    )


# Allow running as standalone script
if __name__ == "__main__":
    # Generate 2 separate generators (generators are single-pass)
    save_to_json_streaming(generate_mock_tweets(count=30), "output/mock_tweets.json")
    save_to_csv_streaming(generate_mock_tweets(count=30), "output/mock_tweets.csv")
    gc.collect()  # MEM: force garbage collection after batch
    print("Generated 30 mock tweets → output/mock_tweets.json, output/mock_tweets.csv")
