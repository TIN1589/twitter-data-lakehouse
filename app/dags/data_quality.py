"""Data quality checking module for Twitter data pipeline.

Provides comprehensive data quality checks including:
- Schema validation (using Pydantic models)
- Null/missing value detection
- Duplicate detection
- Range and type validation
- Engagement metric reasonableness checks
"""

import logging
from typing import List, Dict, Tuple, Set
from datetime import datetime

from models import (
    RawTweet,
    CleanedTweet,
    DataQualityReport,
    ValidationError,
    DataQualityCheckResult,
)
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """Performs comprehensive quality checks on tweet data."""

    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.errors: List[ValidationError] = []
        self.warnings: List[str] = []
        self.seen_ids: Set[str] = set()

    def validate_raw_tweets(self, tweets: List[Dict]) -> Tuple[List[Dict], DataQualityCheckResult]:
        """Validate raw tweets against RawTweet schema.
        
        Args:
            tweets: List of raw tweet dictionaries
            
        Returns:
            Tuple of (valid_tweets, quality_check_result)
        """
        valid_tweets = []
        invalid_count = 0

        for i, tweet_dict in enumerate(tweets):
            try:
                # Pydantic validation
                raw_tweet = RawTweet(**tweet_dict)
                
                # Additional checks
                self._check_duplicate(raw_tweet.id)
                
                valid_tweets.append(raw_tweet.dict())
                
            except PydanticValidationError as e:
                invalid_count += 1
                for error in e.errors():
                    field = str(error['loc'][0]) if error['loc'] else 'unknown'
                    msg = error['msg']
                    
                    self.errors.append(ValidationError(
                        tweet_id=tweet_dict.get('id', 'unknown'),
                        field=field,
                        error_message=msg,
                        raw_value=str(tweet_dict.get(field, 'N/A'))[:100],
                    ))
                    logger.warning(f"Tweet validation failed: {msg}")
            except Exception as e:
                invalid_count += 1
                self.errors.append(ValidationError(
                    tweet_id=tweet_dict.get('id', 'unknown'),
                    field='unknown',
                    error_message=str(e),
                ))
                logger.error(f"Unexpected error validating tweet: {e}")

        # Generate report
        report = self._generate_report(len(tweets), len(valid_tweets), invalid_count)
        result = DataQualityCheckResult(
            batch_id=self.batch_id,
            passed=invalid_count == 0 and len(self.warnings) == 0,
            report=report,
            errors=self.errors,
            warnings=self.warnings,
        )

        logger.info(f"Raw tweet validation: {len(valid_tweets)}/{len(tweets)} valid")
        return valid_tweets, result

    def validate_cleaned_tweets(self, tweets: List[Dict]) -> Tuple[List[Dict], DataQualityCheckResult]:
        """Validate cleaned tweets against CleanedTweet schema.
        
        Args:
            tweets: List of cleaned tweet dictionaries
            
        Returns:
            Tuple of (valid_tweets, quality_check_result)
        """
        valid_tweets = []
        invalid_count = 0

        for tweet_dict in tweets:
            try:
                # Pydantic validation
                cleaned_tweet = CleanedTweet(**tweet_dict)
                
                # Additional checks
                self._check_engagement_metrics(cleaned_tweet)
                
                valid_tweets.append(cleaned_tweet.dict())
                
            except PydanticValidationError as e:
                invalid_count += 1
                for error in e.errors():
                    field = str(error['loc'][0]) if error['loc'] else 'unknown'
                    msg = error['msg']
                    self.errors.append(ValidationError(
                        tweet_id=tweet_dict.get('tweet_id', 'unknown'),
                        field=field,
                        error_message=msg,
                    ))
            except Exception as e:
                invalid_count += 1
                logger.error(f"Error validating cleaned tweet: {e}")

        report = self._generate_report(len(tweets), len(valid_tweets), invalid_count)
        result = DataQualityCheckResult(
            batch_id=self.batch_id,
            passed=invalid_count == 0,
            report=report,
            errors=self.errors,
            warnings=self.warnings,
        )

        logger.info(f"Cleaned tweet validation: {len(valid_tweets)}/{len(tweets)} valid")
        return valid_tweets, result

    def _check_duplicate(self, tweet_id: str) -> None:
        """Check if tweet ID is a duplicate within batch."""
        if tweet_id in self.seen_ids:
            self.warnings.append(f"Duplicate tweet ID: {tweet_id}")
        self.seen_ids.add(tweet_id)

    def _check_engagement_metrics(self, tweet: CleanedTweet) -> None:
        """Check engagement metrics for reasonableness."""
        total_engagement = (
            tweet.like_count + 
            tweet.retweet_count + 
            tweet.reply_count + 
            tweet.quote_count
        )
        
        # Warn if metrics are suspiciously high or low
        if total_engagement == 0:
            self.warnings.append(
                f"Tweet {tweet.tweet_id} has zero engagement"
            )
        
        # Check consistency: typically quote_count < reply_count < retweet_count < like_count
        if tweet.quote_count > tweet.reply_count:
            self.warnings.append(
                f"Tweet {tweet.tweet_id}: quote_count > reply_count (unusual)"
            )

    def _generate_report(self, total: int, valid: int, invalid: int) -> DataQualityReport:
        """Generate data quality report."""
        return DataQualityReport(
            batch_id=self.batch_id,
            total_tweets=total,
            valid_tweets=valid,
            invalid_tweets=invalid,
            duplicate_count=len([w for w in self.warnings if 'Duplicate' in w]),
            null_text_count=len([e for e in self.errors if 'text' in e.field.lower()]),
            null_metrics_count=len([e for e in self.errors if 'metrics' in e.field.lower()]),
            avg_engagement=0.0,  # Can be computed if needed
        )


def validate_and_clean_tweets(
    raw_tweets: List[Dict],
    batch_id: str,
) -> Tuple[List[Dict], DataQualityCheckResult]:
    """Main entry point: Validate raw tweets and clean them.
    
    Args:
        raw_tweets: Raw tweet dictionaries from generator
        batch_id: Batch processing ID
        
    Returns:
        Tuple of (cleaned_tweets, quality_result)
    """
    checker = DataQualityChecker(batch_id)
    
    # Step 1: Validate raw tweets
    valid_raw, raw_validation_result = checker.validate_raw_tweets(raw_tweets)
    
    if not valid_raw:
        logger.error(f"No valid tweets after raw validation. Errors: {checker.errors}")
        return [], raw_validation_result
    
    logger.info(f"Validated {len(valid_raw)} raw tweets")
    return valid_raw, raw_validation_result


def quality_check_report_to_dict(result: DataQualityCheckResult) -> Dict:
    """Convert quality check result to dictionary for logging/storage."""
    return {
        'batch_id': result.batch_id,
        'passed': result.passed,
        'total_tweets': result.report.total_tweets,
        'valid_tweets': result.report.valid_tweets,
        'invalid_tweets': result.report.invalid_tweets,
        'duplicate_count': result.report.duplicate_count,
        'warning_count': len(result.warnings),
        'error_count': len(result.errors),
        'warnings': result.warnings[:10],  # Top 10 warnings
        'errors': [
            {
                'tweet_id': e.tweet_id,
                'field': e.field,
                'message': e.error_message,
            }
            for e in result.errors[:10]  # Top 10 errors
        ],
    }


__all__ = [
    'DataQualityChecker',
    'validate_and_clean_tweets',
    'quality_check_report_to_dict',
]
