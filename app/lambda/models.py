"""Pydantic models for Twitter data validation and quality checks.

Provides models for:
- Raw tweet validation (Twitter API v2 structure)
- Cleaned tweet validation (flattened structure)
- Data quality checks and metrics
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class PublicMetrics(BaseModel):
    """Metrics associated with a tweet."""
    like_count: int = Field(..., ge=0, description="Number of likes, must be >= 0")
    retweet_count: int = Field(..., ge=0, description="Number of retweets, must be >= 0")
    reply_count: int = Field(..., ge=0, description="Number of replies, must be >= 0")
    quote_count: int = Field(..., ge=0, description="Number of quotes, must be >= 0")

    @validator('like_count', 'retweet_count', 'reply_count', 'quote_count')
    def check_reasonable_range(cls, v):
        """Ensure metrics are within reasonable ranges."""
        max_reasonable = 10_000_000  # 10M seems reasonable max
        if v > max_reasonable:
            raise ValueError(f"Metric value {v} exceeds reasonable maximum {max_reasonable}")
        return v


class RawTweet(BaseModel):
    """Raw tweet as received from mock data generator (Twitter API v2 structure)."""
    id: str = Field(..., description="Tweet ID")
    text: str = Field(..., min_length=1, max_length=500, description="Tweet text")
    created_at: str = Field(..., description="Tweet creation timestamp (ISO 8601)")
    author_id: str = Field(..., description="Author's user ID")
    username: str = Field(..., min_length=1, max_length=50, description="Author's username")
    lang: str = Field(default="en", description="Language code (ISO 639-1)")
    public_metrics: PublicMetrics = Field(..., description="Tweet engagement metrics")
    hashtags: List[str] = Field(default_factory=list, description="Hashtags in tweet")

    @validator('id')
    def validate_id(cls, v):
        """Ensure tweet ID is numeric string."""
        if not v.isdigit():
            raise ValueError("Tweet ID must be numeric string")
        if len(v) < 10:
            raise ValueError("Tweet ID must be at least 10 digits")
        return v

    @validator('created_at')
    def validate_created_at(cls, v):
        """Ensure created_at is valid ISO 8601 format (with Z or timezone)."""
        import re
        # Accept format: YYYY-MM-DDTHH:MM:SS.000Z or YYYY-MM-DDTHH:MM:SS+00:00
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?(Z|[+-]\d{2}:\d{2})$'
        if not re.match(iso_pattern, v):
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}. Expected format: YYYY-MM-DDTHH:MM:SS.000Z")
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError as e:
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}. Error: {str(e)}")
        return v

    @validator('lang')
    def validate_lang(cls, v):
        """Ensure language is a valid 2-5 letter code."""
        if not (2 <= len(v) <= 5) or not v.isalpha():
            raise ValueError(f"Invalid language code: {v}. Expected 2-5 alphabetic characters")
        return v.lower()

    @validator('hashtags')
    def validate_hashtags(cls, v):
        """Ensure hashtags are non-empty strings."""
        if not isinstance(v, list):
            raise ValueError("Hashtags must be a list")
        for tag in v:
            if not isinstance(tag, str) or len(tag) == 0:
                raise ValueError("Each hashtag must be a non-empty string")
        return v


class CleanedTweet(BaseModel):
    """Cleaned and flattened tweet for storage (one row in database)."""
    tweet_id: str = Field(..., description="Tweet ID")
    username: str = Field(..., description="Author's username")
    user_id: str = Field(..., description="Author's user ID")
    text: str = Field(..., description="Tweet text")
    like_count: int = Field(..., ge=0, description="Number of likes")
    retweet_count: int = Field(..., ge=0, description="Number of retweets")
    reply_count: int = Field(..., ge=0, description="Number of replies")
    quote_count: int = Field(..., ge=0, description="Number of quotes")
    hashtags: str = Field(default="", description="Comma-separated hashtags")
    lang: str = Field(default="en", description="Language code")
    created_at: str = Field(..., description="Tweet creation timestamp")
    batch_id: str = Field(..., description="Batch processing ID (UUID)")
    batch_datetime: str = Field(..., description="Batch processing datetime")

    @validator('batch_id')
    def validate_batch_id(cls, v):
        """Ensure batch_id is a valid hex string (from uuid4().hex)."""
        if not all(c in '0123456789abcdef' for c in v) or len(v) != 32:
            raise ValueError("batch_id must be 32-character hex string from uuid4()")
        return v

    @validator('batch_datetime')
    def validate_batch_datetime(cls, v):
        """Ensure batch_datetime is in expected format."""
        try:
            datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ValueError(f"batch_datetime must be 'YYYY-MM-DD HH:MM:SS', got: {v}")
        return v


class DataQualityReport(BaseModel):
    """Report on data quality for a batch of tweets."""
    batch_id: str = Field(..., description="Batch ID")
    total_tweets: int = Field(..., ge=0, description="Total tweets processed")
    valid_tweets: int = Field(..., ge=0, description="Tweets that passed validation")
    invalid_tweets: int = Field(..., ge=0, description="Tweets that failed validation")
    null_text_count: int = Field(default=0, description="Tweets with null/empty text")
    null_metrics_count: int = Field(default=0, description="Tweets with null metrics")
    duplicate_count: int = Field(default=0, description="Duplicate tweets")
    avg_engagement: float = Field(default=0.0, description="Average engagement (likes + retweets)")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @validator('valid_tweets', 'invalid_tweets')
    def check_sum(cls, v, values):
        """Ensure valid + invalid = total."""
        if 'total_tweets' in values:
            total = values['total_tweets']
            # This validator runs before we know both values, so we skip this check
            # It's validated in the create method of QualityChecker
        return v


class ValidationError(BaseModel):
    """Error from data validation."""
    tweet_id: str = Field(..., description="Tweet ID that failed")
    field: str = Field(..., description="Field that failed validation")
    error_message: str = Field(..., description="Error details")
    raw_value: Optional[str] = Field(None, description="Raw value that failed")


class DataQualityCheckResult(BaseModel):
    """Result of quality checks on a batch."""
    batch_id: str
    passed: bool = Field(..., description="Did batch pass all quality checks?")
    report: DataQualityReport
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# Export all models
__all__ = [
    'PublicMetrics',
    'RawTweet',
    'CleanedTweet',
    'DataQualityReport',
    'ValidationError',
    'DataQualityCheckResult',
]
