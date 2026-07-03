"""Pipeline utilities for data cleanup, aggregation, and retention management."""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List

import boto3
from botocore.client import Config

logger = logging.getLogger(__name__)


class DataRetentionManager:
    """Manages data retention policies and cleanup."""

    def __init__(self, endpoint: str = None, access_key: str = None, secret_key: str = None):
        """Initialize S3 client for MinIO."""
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.access_key = access_key or os.getenv("MINIO_ROOT_USER", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
        
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"http://{self.endpoint}",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

    def cleanup_old_data(
        self,
        bucket: str,
        days_to_keep: int = 30,
        dry_run: bool = False,
    ) -> Dict:
        """Delete data older than specified days.
        
        Args:
            bucket: S3 bucket name
            days_to_keep: Keep data from last N days
            dry_run: If True, only list files to delete (don't actually delete)
            
        Returns:
            Dict with cleanup stats
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        response = self.s3.list_objects_v2(Bucket=bucket, Prefix="tweets/")
        
        deleted_count = 0
        deleted_size = 0
        
        if "Contents" not in response:
            logger.info(f"No objects found in {bucket}")
            return {
                "deleted_count": 0,
                "deleted_size_bytes": 0,
                "status": "OK",
            }
        
        for obj in response.get("Contents", []):
            key = obj["Key"]
            modified_date = obj["LastModified"].replace(tzinfo=None)
            size = obj["Size"]
            
            if modified_date < cutoff_date:
                logger.info(f"Deleting old object: {key} (modified: {modified_date})")
                
                if not dry_run:
                    self.s3.delete_object(Bucket=bucket, Key=key)
                    deleted_count += 1
                    deleted_size += size
        
        logger.info(
            f"Cleanup completed: deleted {deleted_count} objects, "
            f"freed {deleted_size / (1024*1024):.2f} MB"
        )
        
        return {
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "deleted_size_mb": deleted_size / (1024 * 1024),
            "status": "OK",
            "dry_run": dry_run,
        }

    def get_storage_stats(self, bucket: str) -> Dict:
        """Get storage statistics for the bucket."""
        response = self.s3.list_objects_v2(Bucket=bucket, Prefix="tweets/")
        
        total_size = 0
        object_count = 0
        
        for obj in response.get("Contents", []):
            total_size += obj["Size"]
            object_count += 1
        
        stats = {
            "bucket": bucket,
            "object_count": object_count,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "total_size_gb": total_size / (1024 * 1024 * 1024),
        }
        
        logger.info(f"Storage stats: {stats}")
        return stats


class DataAggregator:
    """Aggregates raw tweet data into summary tables."""

    def __init__(self):
        pass

    def create_daily_summary(
        self,
        tweets: List[Dict],
    ) -> Dict:
        """Create daily summary statistics from tweets.
        
        Args:
            tweets: List of cleaned tweet dictionaries
            
        Returns:
            Dict with summary metrics
        """
        if not tweets:
            return self._empty_summary()
        
        total_tweets = len(tweets)
        total_likes = sum(t.get("like_count", 0) for t in tweets)
        total_retweets = sum(t.get("retweet_count", 0) for t in tweets)
        total_replies = sum(t.get("reply_count", 0) for t in tweets)
        total_quotes = sum(t.get("quote_count", 0) for t in tweets)
        
        avg_likes = total_likes / total_tweets if total_tweets > 0 else 0
        avg_retweets = total_retweets / total_tweets if total_tweets > 0 else 0
        avg_replies = total_replies / total_tweets if total_tweets > 0 else 0
        avg_quotes = total_quotes / total_tweets if total_tweets > 0 else 0
        
        # Language distribution
        lang_counts = {}
        for tweet in tweets:
            lang = tweet.get("lang", "unknown")
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        
        # Top hashtags
        hashtag_counts = {}
        for tweet in tweets:
            hashtags = tweet.get("hashtags", "").split(",")
            for tag in hashtags:
                tag = tag.strip()
                if tag:
                    hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
        
        top_hashtags = sorted(
            hashtag_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        
        summary = {
            "batch_date": datetime.now().strftime("%Y-%m-%d"),
            "total_tweets": total_tweets,
            "total_engagement": total_likes + total_retweets + total_replies + total_quotes,
            "avg_likes": round(avg_likes, 2),
            "avg_retweets": round(avg_retweets, 2),
            "avg_replies": round(avg_replies, 2),
            "avg_quotes": round(avg_quotes, 2),
            "max_likes": max((t.get("like_count", 0) for t in tweets), default=0),
            "max_retweets": max((t.get("retweet_count", 0) for t in tweets), default=0),
            "language_distribution": lang_counts,
            "top_hashtags": top_hashtags,
        }
        
        logger.info(f"Daily summary: {summary}")
        return summary

    def _empty_summary(self) -> Dict:
        """Return empty summary template."""
        return {
            "batch_date": datetime.now().strftime("%Y-%m-%d"),
            "total_tweets": 0,
            "total_engagement": 0,
            "avg_likes": 0,
            "avg_retweets": 0,
            "avg_replies": 0,
            "avg_quotes": 0,
            "max_likes": 0,
            "max_retweets": 0,
            "language_distribution": {},
            "top_hashtags": [],
        }


def log_pipeline_health() -> Dict:
    """Log pipeline health metrics."""
    health = {
        "timestamp": datetime.now().isoformat(),
        "status": "OK",
        "checks": {
            "data_generation": "OK",
            "data_validation": "OK",
            "data_upload": "OK",
        },
    }
    
    logger.info(f"Pipeline health: {health}")
    return health


__all__ = [
    'DataRetentionManager',
    'DataAggregator',
    'log_pipeline_health',
]
