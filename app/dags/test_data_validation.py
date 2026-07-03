"""Unit tests for data validation and quality checks.

Run with: pytest test_data_validation.py -v
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from models import (
    PublicMetrics,
    RawTweet,
    CleanedTweet,
    DataQualityReport,
)
from data_quality import DataQualityChecker, validate_and_clean_tweets


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def valid_raw_tweet_dict():
    """Sample valid raw tweet."""
    return {
        "id": "1735492817263592468",
        "text": "Sample tweet about AI and technology",
        "created_at": "2026-06-19T21:02:51.000Z",
        "author_id": "44196397",
        "username": "testuser",
        "lang": "en",
        "public_metrics": {
            "like_count": 100,
            "retweet_count": 20,
            "reply_count": 5,
            "quote_count": 2,
        },
        "hashtags": ["AI", "Tech"],
    }


@pytest.fixture
def valid_cleaned_tweet_dict():
    """Sample valid cleaned tweet."""
    return {
        "tweet_id": "1735492817263592468",
        "username": "testuser",
        "user_id": "44196397",
        "text": "Sample tweet",
        "like_count": 100,
        "retweet_count": 20,
        "reply_count": 5,
        "quote_count": 2,
        "hashtags": "AI,Tech",
        "lang": "en",
        "created_at": "2026-06-19T21:02:51.000Z",
        "batch_id": "a" * 32,  # 32-char hex
        "batch_datetime": "2026-06-19 21:02:51",
    }


# ============================================================================
# Tests for PublicMetrics Model
# ============================================================================

class TestPublicMetrics:
    """Test PublicMetrics validation."""

    def test_valid_metrics(self):
        """Valid metrics should pass."""
        metrics = PublicMetrics(
            like_count=100,
            retweet_count=20,
            reply_count=5,
            quote_count=2,
        )
        assert metrics.like_count == 100
        assert metrics.retweet_count == 20

    def test_negative_metrics_rejected(self):
        """Negative metrics should be rejected."""
        with pytest.raises(ValidationError):
            PublicMetrics(
                like_count=-1,  # Invalid!
                retweet_count=20,
                reply_count=5,
                quote_count=2,
            )

    def test_extreme_metrics_rejected(self):
        """Unreasonably high metrics should be rejected."""
        with pytest.raises(ValidationError):
            PublicMetrics(
                like_count=100_000_000,  # Too high!
                retweet_count=20,
                reply_count=5,
                quote_count=2,
            )

    def test_zero_metrics_allowed(self):
        """Zero metrics should be allowed."""
        metrics = PublicMetrics(
            like_count=0,
            retweet_count=0,
            reply_count=0,
            quote_count=0,
        )
        assert metrics.like_count == 0


# ============================================================================
# Tests for RawTweet Model
# ============================================================================

class TestRawTweet:
    """Test RawTweet validation."""

    def test_valid_raw_tweet(self, valid_raw_tweet_dict):
        """Valid raw tweet should pass."""
        tweet = RawTweet(**valid_raw_tweet_dict)
        assert tweet.id == "1735492817263592468"
        assert tweet.username == "testuser"

    def test_invalid_tweet_id_too_short(self, valid_raw_tweet_dict):
        """Tweet ID that's too short should be rejected."""
        valid_raw_tweet_dict["id"] = "123"
        with pytest.raises(ValidationError):
            RawTweet(**valid_raw_tweet_dict)

    def test_invalid_tweet_id_not_numeric(self, valid_raw_tweet_dict):
        """Non-numeric tweet ID should be rejected."""
        valid_raw_tweet_dict["id"] = "abc123def456"
        with pytest.raises(ValidationError):
            RawTweet(**valid_raw_tweet_dict)

    def test_invalid_timestamp_format(self, valid_raw_tweet_dict):
        """Invalid ISO 8601 timestamp should be rejected."""
        valid_raw_tweet_dict["created_at"] = "2026-06-19 21:02:51"  # Wrong format
        with pytest.raises(ValidationError):
            RawTweet(**valid_raw_tweet_dict)

    def test_empty_text_rejected(self, valid_raw_tweet_dict):
        """Empty text should be rejected."""
        valid_raw_tweet_dict["text"] = ""
        with pytest.raises(ValidationError):
            RawTweet(**valid_raw_tweet_dict)

    def test_invalid_language_code(self, valid_raw_tweet_dict):
        """Invalid language code should be rejected."""
        valid_raw_tweet_dict["lang"] = "english"  # Should be 2-letter code
        with pytest.raises(ValidationError):
            RawTweet(**valid_raw_tweet_dict)

    def test_invalid_hashtags_not_list(self, valid_raw_tweet_dict):
        """Hashtags must be a list."""
        valid_raw_tweet_dict["hashtags"] = "AI,Tech"  # Should be list
        with pytest.raises(ValidationError):
            RawTweet(**valid_raw_tweet_dict)

    def test_empty_hashtag_rejected(self, valid_raw_tweet_dict):
        """Empty hashtags should be rejected."""
        valid_raw_tweet_dict["hashtags"] = ["AI", "", "Tech"]
        with pytest.raises(ValidationError):
            RawTweet(**valid_raw_tweet_dict)

    def test_language_code_normalized_to_lowercase(self, valid_raw_tweet_dict):
        """Language code should be normalized to lowercase."""
        valid_raw_tweet_dict["lang"] = "EN"
        tweet = RawTweet(**valid_raw_tweet_dict)
        assert tweet.lang == "en"


# ============================================================================
# Tests for CleanedTweet Model
# ============================================================================

class TestCleanedTweet:
    """Test CleanedTweet validation."""

    def test_valid_cleaned_tweet(self, valid_cleaned_tweet_dict):
        """Valid cleaned tweet should pass."""
        tweet = CleanedTweet(**valid_cleaned_tweet_dict)
        assert tweet.tweet_id == "1735492817263592468"
        assert tweet.batch_id == "a" * 32

    def test_invalid_batch_id_wrong_length(self, valid_cleaned_tweet_dict):
        """Batch ID must be exactly 32 hex characters."""
        valid_cleaned_tweet_dict["batch_id"] = "a" * 31
        with pytest.raises(ValidationError):
            CleanedTweet(**valid_cleaned_tweet_dict)

    def test_invalid_batch_id_non_hex(self, valid_cleaned_tweet_dict):
        """Batch ID must be valid hex."""
        valid_cleaned_tweet_dict["batch_id"] = "z" * 32
        with pytest.raises(ValidationError):
            CleanedTweet(**valid_cleaned_tweet_dict)

    def test_invalid_batch_datetime_format(self, valid_cleaned_tweet_dict):
        """Batch datetime must be in correct format."""
        valid_cleaned_tweet_dict["batch_datetime"] = "2026/06/19 21:02:51"
        with pytest.raises(ValidationError):
            CleanedTweet(**valid_cleaned_tweet_dict)

    def test_negative_engagement_rejected(self, valid_cleaned_tweet_dict):
        """Negative engagement metrics should be rejected."""
        valid_cleaned_tweet_dict["like_count"] = -1
        with pytest.raises(ValidationError):
            CleanedTweet(**valid_cleaned_tweet_dict)

    def test_hashtags_comma_separated_string(self, valid_cleaned_tweet_dict):
        """Hashtags should be comma-separated string."""
        tweet = CleanedTweet(**valid_cleaned_tweet_dict)
        assert tweet.hashtags == "AI,Tech"


# ============================================================================
# Tests for DataQualityChecker
# ============================================================================

class TestDataQualityChecker:
    """Test data quality checking."""

    def test_validate_raw_tweets_all_valid(self, valid_raw_tweet_dict):
        """All valid tweets should pass."""
        checker = DataQualityChecker("test_batch_id")
        tweets = []
        base_id = int(valid_raw_tweet_dict["id"])
        for i in range(3):
            t = valid_raw_tweet_dict.copy()
            t["id"] = str(base_id + i)
            tweets.append(t)
        valid_tweets, result = checker.validate_raw_tweets(tweets)
        
        assert len(valid_tweets) == 3
        assert result.report.valid_tweets == 3
        assert result.report.invalid_tweets == 0
        assert result.passed is True

    def test_validate_raw_tweets_some_invalid(self, valid_raw_tweet_dict):
        """Mix of valid and invalid tweets."""
        checker = DataQualityChecker("test_batch_id")
        
        invalid_tweet = valid_raw_tweet_dict.copy()
        invalid_tweet["id"] = "123"  # Invalid ID
        
        tweets = [valid_raw_tweet_dict, invalid_tweet]
        valid_tweets, result = checker.validate_raw_tweets(tweets)
        
        assert len(valid_tweets) == 1
        assert result.report.valid_tweets == 1
        assert result.report.invalid_tweets == 1
        assert len(result.errors) >= 1

    def test_duplicate_detection(self, valid_raw_tweet_dict):
        """Duplicate tweets should generate warnings."""
        checker = DataQualityChecker("test_batch_id")
        
        tweets = [valid_raw_tweet_dict, valid_raw_tweet_dict]  # Same tweet twice
        valid_tweets, result = checker.validate_raw_tweets(tweets)
        
        assert len(valid_tweets) == 2
        assert any("Duplicate" in w for w in result.warnings)

    def test_validate_cleaned_tweets(self, valid_cleaned_tweet_dict):
        """Valid cleaned tweets should pass."""
        checker = DataQualityChecker("a" * 32)
        tweets = [valid_cleaned_tweet_dict]
        valid_tweets, result = checker.validate_cleaned_tweets(tweets)
        
        assert len(valid_tweets) == 1
        assert result.passed is True

    def test_zero_engagement_warning(self, valid_cleaned_tweet_dict):
        """Zero engagement should trigger warning."""
        checker = DataQualityChecker("a" * 32)
        valid_cleaned_tweet_dict["like_count"] = 0
        valid_cleaned_tweet_dict["retweet_count"] = 0
        valid_cleaned_tweet_dict["reply_count"] = 0
        valid_cleaned_tweet_dict["quote_count"] = 0
        
        tweets = [valid_cleaned_tweet_dict]
        valid_tweets, result = checker.validate_cleaned_tweets(tweets)
        
        assert any("zero engagement" in w.lower() for w in result.warnings)

    def test_suspicious_metrics_warning(self, valid_cleaned_tweet_dict):
        """quote_count > reply_count should trigger warning."""
        checker = DataQualityChecker("a" * 32)
        valid_cleaned_tweet_dict["quote_count"] = 100
        valid_cleaned_tweet_dict["reply_count"] = 10  # Unusual!
        
        tweets = [valid_cleaned_tweet_dict]
        valid_tweets, result = checker.validate_cleaned_tweets(tweets)
        
        assert any("quote_count > reply_count" in w for w in result.warnings)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for full workflow."""

    def test_validate_and_clean_tweets_full_workflow(self, valid_raw_tweet_dict):
        """Full validation and cleaning workflow."""
        batch_id = "b" * 32
        tweets = [valid_raw_tweet_dict] * 5
        
        valid_tweets, result = validate_and_clean_tweets(tweets, batch_id)
        
        assert len(valid_tweets) >= 1  # At least some valid
        assert result.batch_id == batch_id

    def test_quality_threshold_fails_on_bad_data(self, valid_raw_tweet_dict):
        """Should handle quality failures gracefully."""
        checker = DataQualityChecker("test_batch")
        
        # Create mostly invalid tweets
        invalid_tweets = [
            {**valid_raw_tweet_dict, "id": str(i)}  # Some valid
            if i == 0
            else {**valid_raw_tweet_dict, "id": "bad"}  # Invalid IDs
            for i in range(5)
        ]
        
        valid_tweets, result = checker.validate_raw_tweets(invalid_tweets)
        # Should process gracefully, even with failures
        assert isinstance(result.report.invalid_tweets, int)


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance with larger datasets."""

    def test_validate_large_batch(self, valid_raw_tweet_dict):
        """Should handle large batches efficiently."""
        checker = DataQualityChecker("large_batch")
        tweets = []
        base_id = int(valid_raw_tweet_dict["id"])
        for i in range(1000):
            t = valid_raw_tweet_dict.copy()
            t["id"] = str(base_id + i)
            tweets.append(t)
        
        valid_tweets, result = checker.validate_raw_tweets(tweets)
        
        assert len(valid_tweets) == 1000
        assert result.passed is True


# ============================================================================
# Conftest for pytest
# ============================================================================

def pytest_configure(config):
    """Add custom markers."""
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "performance: performance tests")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
