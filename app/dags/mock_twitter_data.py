"""Mock Twitter Data Generator.

Generates fake tweet data with realistic structure for the Data Lakehouse pipeline.
Used as a replacement for Twitter API (no Bearer Token required).
"""

import csv
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


def generate_mock_tweets(count=20):
    """Generate a list of mock tweet dictionaries.

    Args:
        count: Number of tweets to generate.

    Returns:
        List of tweet dicts matching Twitter API v2 structure.
    """
    tweets = []
    base_time = datetime.utcnow()

    for i in range(count):
        created_at = base_time - timedelta(
            minutes=random.randint(1, 1440),
            seconds=random.randint(0, 59),
        )
        tweet = {
            "id": str(random.randint(10**17, 10**18 - 1)),
            "text": random.choice(SAMPLE_TEXTS),
            "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "author_id": "44196397",
            "username": "elonmusk",
            "lang": random.choice(["en", "en", "en", "es", "fr"]),  # Mostly English
            "public_metrics": {
                "like_count": random.randint(500, 800000),
                "retweet_count": random.randint(100, 200000),
                "reply_count": random.randint(50, 80000),
                "quote_count": random.randint(10, 30000),
            },
            "hashtags": random.choice(SAMPLE_HASHTAGS_POOL),
        }
        tweets.append(tweet)

    return tweets


def flatten_tweets(tweets):
    """Flatten nested tweet dicts for CSV/tabular storage."""
    flat_list = []
    for t in tweets:
        flat = {
            "id": t["id"],
            "text": t["text"],
            "created_at": t["created_at"],
            "author_id": t["author_id"],
            "username": t["username"],
            "lang": t["lang"],
            "like_count": t["public_metrics"]["like_count"],
            "retweet_count": t["public_metrics"]["retweet_count"],
            "reply_count": t["public_metrics"]["reply_count"],
            "quote_count": t["public_metrics"]["quote_count"],
            "hashtags": ",".join(t.get("hashtags", [])),
        }
        flat_list.append(flat)
    return flat_list


def save_to_json(tweets, filepath):
    """Save tweets as JSON file."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(tweets, f, indent=2, ensure_ascii=False)


def save_to_csv(tweets, filepath):
    """Save flattened tweets as CSV file."""
    flat = flatten_tweets(tweets)
    if not flat:
        return
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flat[0].keys())
        writer.writeheader()
        writer.writerows(flat)


def upload_to_minio_boto3(file_bytes, bucket_name, object_key, content_type="application/octet-stream"):
    """Upload bytes to MinIO bucket using boto3.

    Args:
        file_bytes: File content as bytes.
        bucket_name: Target MinIO bucket name.
        object_key: S3 object key (path in bucket).
        content_type: MIME type of the file.
    """
    import boto3
    from botocore.client import Config

    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://{endpoint}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )

    # Create bucket if it doesn't exist
    try:
        s3.head_bucket(Bucket=bucket_name)
    except Exception:
        s3.create_bucket(Bucket=bucket_name)

    s3.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=file_bytes,
        ContentType=content_type,
    )


# Allow running as standalone script
if __name__ == "__main__":
    tweets = generate_mock_tweets(count=30)
    save_to_json(tweets, "output/mock_tweets.json")
    save_to_csv(tweets, "output/mock_tweets.csv")
    print(f"Generated {len(tweets)} mock tweets → output/mock_tweets.json, output/mock_tweets.csv")
