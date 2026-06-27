"""Mock Twitter Data Generator — Memory-Optimized, Multi-User.

Generates fake tweet data using Python generators (yield).
NO Pandas, NO large in-memory lists. Data is streamed chunk-by-chunk.
Optimized for AWS EC2 t3.micro (1GB RAM + 4GB Swap).

Features:
- Multiple realistic Twitter users (not just one)
- Diverse tweet content across tech, business, science
- Realistic engagement metrics based on follower count
"""

import csv
import gc
import io
import json
import os
import random
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Multi-user profiles — realistic Twitter accounts
# ---------------------------------------------------------------------------
USERS = [
    {"author_id": "44196397", "username": "elonmusk", "followers": 180_000_000},
    {"author_id": "813286", "username": "BarackObama", "followers": 133_000_000},
    {"author_id": "15846407", "username": "BillGates", "followers": 63_000_000},
    {"author_id": "50393960", "username": "BillNye", "followers": 6_800_000},
    {"author_id": "17919972", "username": "sundaboreng", "followers": 12_000_000},
    {"author_id": "1aboreng5", "username": "NASA", "followers": 97_000_000},
    {"author_id": "783214", "username": "Twitter", "followers": 65_000_000},
    {"author_id": "34713362", "username": "samaltman", "followers": 3_200_000},
]

# Diverse tweet content — tech, science, business, social
SAMPLE_TEXTS = [
    # Tech / AI
    "Just had an incredible meeting about the future of AI. The possibilities are truly endless! 🚀",
    "AI safety is one of the most important issues of our time. We need to get this right.",
    "Neural networks are getting smarter. The implications are profound.",
    "Open source AI will democratize technology for everyone on the planet.",
    "The pace of AI development is unprecedented. We need thoughtful regulation.",
    "Large language models are changing how we interact with technology fundamentally.",
    "Just tested the latest AI model. The reasoning capabilities are remarkable.",
    # Space
    "SpaceX Starship test flight was amazing today. One step closer to Mars! 🌟",
    "Mars is looking more achievable every day. Humanity's future is multiplanetary.",
    "Space exploration inspires the next generation of scientists and engineers.",
    "Rocket landing success rate keeps improving. Reusability is the future of space.",
    "New telescope data reveals thousands of potentially habitable exoplanets 🔭",
    # Energy / Climate
    "The future of sustainable energy is here. Solar + batteries will change everything.",
    "Battery technology is the key to solving climate change. We're making progress.",
    "Renewable energy adoption is accelerating faster than anyone predicted.",
    "Electric vehicles are not just better for the environment, they're better cars. Period.",
    "Climate action requires both innovation and policy. We need both working together.",
    # Business / Innovation
    "Tesla just broke another delivery record this quarter. Proud of the entire team! ⚡",
    "Innovation happens when you push boundaries and refuse to accept the status quo.",
    "Building the machine that builds the machine. That's the real challenge.",
    "Every great company was once a startup with a crazy idea.",
    "The best part of my job is working with incredibly talented people every day.",
    "Startup founders: focus on building something people actually want, not fundraising.",
    # Science / Education
    "Engineering is the closest thing to magic that exists in this world.",
    "Science literacy is fundamental to a functioning democracy. Invest in education.",
    "The James Webb Space Telescope continues to rewrite our understanding of the cosmos.",
    "Vaccines remain one of humanity's greatest achievements. Science saves lives.",
    # Social / Policy
    "Free speech is the bedrock of a functioning democracy.",
    "Education is the most powerful tool we have to change the world.",
    "Access to clean water and sanitation should be a basic human right everywhere.",
    "The digital divide is real. We need to ensure technology benefits everyone.",
]

SAMPLE_HASHTAGS_POOL = [
    ["AI", "FutureTech", "MachineLearning"],
    ["SpaceX", "Mars", "Space"],
    ["Tesla", "EV", "ElectricVehicles"],
    ["Energy", "Solar", "Sustainability"],
    ["Innovation", "Tech", "Startups"],
    ["Starlink", "Internet", "Satellite"],
    ["Engineering", "Science", "STEM"],
    ["FSD", "Autopilot", "SelfDriving"],
    ["ClimateChange", "CleanEnergy", "NetZero"],
    ["OpenSource", "AI", "LLM"],
    ["Education", "Learning", "Future"],
    ["NASA", "Astronomy", "JamesWebb"],
]

# --- CSV column definition (single source of truth) ---
CSV_FIELDNAMES = [
    "id", "text", "created_at", "author_id", "username",
    "lang", "like_count", "retweet_count", "reply_count",
    "quote_count", "hashtags", "batch_id", "batch_datetime",
]


def generate_mock_tweets(count=50):
    """Generator: yields one mock tweet dict at a time.

    >>> MEM: O(1) per tweet instead of O(N) for entire list.
    Now with multiple users and follower-scaled engagement metrics.
    """
    base_time = datetime.utcnow()

    for _ in range(count):
        user = random.choice(USERS)
        # Scale engagement metrics by follower count (more realistic)
        follower_scale = user["followers"] / 100_000_000
        created_at = base_time - timedelta(
            minutes=random.randint(1, 4320),  # Up to 3 days back
            seconds=random.randint(0, 59),
        )
        yield {
            "id": str(random.randint(10**17, 10**18 - 1)),
            "text": random.choice(SAMPLE_TEXTS),
            "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "author_id": user["author_id"],
            "username": user["username"],
            "lang": random.choice(["en", "en", "en", "en", "es", "fr", "ja", "pt"]),
            "public_metrics": {
                "like_count": int(random.randint(100, 500000) * follower_scale),
                "retweet_count": int(random.randint(50, 150000) * follower_scale),
                "reply_count": int(random.randint(20, 50000) * follower_scale),
                "quote_count": int(random.randint(5, 20000) * follower_scale),
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


# Allow running as standalone script
if __name__ == "__main__":
    save_to_json_streaming(generate_mock_tweets(count=50), "output/mock_tweets.json")
    save_to_csv_streaming(generate_mock_tweets(count=50), "output/mock_tweets.csv")
    gc.collect()
    print("Generated 50 mock tweets → output/mock_tweets.json, output/mock_tweets.csv")
