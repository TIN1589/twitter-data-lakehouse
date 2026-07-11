-- AWS Athena SQL queries for Twitter data analytics
-- These queries are optimized for the Glue Data Catalog database `twitter_lakehouse`
-- and the table `processed` (which is mapped to s3://<bucket-name>/processed/)

-- ============================================================================
-- VIEW 1: Daily Tweet Summary
-- Purpose: Pre-aggregated daily stats for fast dashboard queries
-- ============================================================================

CREATE OR REPLACE VIEW daily_tweet_summary AS
SELECT
  SUBSTR(created_at, 1, 10) AS tweet_date,
  lang,
  COUNT(*) AS total_tweets,
  SUM(like_count) AS total_likes,
  SUM(retweet_count) AS total_retweets,
  SUM(reply_count) AS total_replies,
  SUM(quote_count) AS total_quotes,
  SUM(like_count + retweet_count + reply_count + quote_count) AS total_engagement,
  ROUND(AVG(CAST(like_count AS DOUBLE)), 2) AS avg_likes,
  ROUND(AVG(CAST(retweet_count AS DOUBLE)), 2) AS avg_retweets,
  ROUND(AVG(CAST(reply_count AS DOUBLE)), 2) AS avg_replies,
  ROUND(AVG(CAST(quote_count AS DOUBLE)), 2) AS avg_quotes,
  MAX(like_count) AS max_likes,
  MAX(retweet_count) AS max_retweets
FROM twitter_lakehouse.processed
GROUP BY SUBSTR(created_at, 1, 10), lang;

-- ============================================================================
-- VIEW 2: Top Hashtags by Engagement
-- Purpose: Quick lookup for trending hashtags
-- ============================================================================

CREATE OR REPLACE VIEW hashtag_performance AS
SELECT
  hashtags,
  COUNT(*) AS tweet_count,
  SUM(like_count) AS total_likes,
  SUM(like_count + retweet_count + reply_count + quote_count) AS total_engagement,
  ROUND(AVG(CAST(like_count AS DOUBLE)), 2) AS avg_likes
FROM twitter_lakehouse.processed
WHERE hashtags IS NOT NULL AND hashtags <> ''
GROUP BY hashtags;

-- ============================================================================
-- VIEW 3: User Performance Rankings
-- Purpose: Top users by engagement
-- ============================================================================

CREATE OR REPLACE VIEW user_performance AS
SELECT
  username,
  user_id,
  COUNT(*) AS tweet_count,
  SUM(like_count) AS total_likes,
  SUM(retweet_count) AS total_retweets,
  SUM(like_count + retweet_count + reply_count + quote_count) AS total_engagement,
  ROUND(AVG(CAST(like_count AS DOUBLE)), 2) AS avg_likes,
  MAX(SUBSTR(created_at, 1, 10)) AS last_tweet_date
FROM twitter_lakehouse.processed
GROUP BY username, user_id;

-- ============================================================================
-- VIEW 4: Language Distribution Trends
-- Purpose: See how tweet distribution changes by language over time
-- ============================================================================

CREATE OR REPLACE VIEW language_trends AS
SELECT
  SUBSTR(created_at, 1, 10) AS tweet_date,
  lang,
  COUNT(*) AS tweet_count,
  SUM(like_count + retweet_count + reply_count + quote_count) AS total_engagement
FROM twitter_lakehouse.processed
GROUP BY SUBSTR(created_at, 1, 10), lang;

-- ============================================================================
-- VIEW 5: Engagement Metrics Distribution
-- Purpose: Understand engagement patterns (percentiles, ranges)
-- ============================================================================

CREATE OR REPLACE VIEW engagement_distribution AS
SELECT
  CASE
    WHEN (like_count + retweet_count + reply_count + quote_count) = 0 THEN 'No Engagement'
    WHEN (like_count + retweet_count + reply_count + quote_count) BETWEEN 1 AND 100 THEN '1-100'
    WHEN (like_count + retweet_count + reply_count + quote_count) BETWEEN 101 AND 1000 THEN '101-1K'
    WHEN (like_count + retweet_count + reply_count + quote_count) BETWEEN 1001 AND 10000 THEN '1K-10K'
    WHEN (like_count + retweet_count + reply_count + quote_count) BETWEEN 10001 AND 100000 THEN '10K-100K'
    ELSE '100K+'
  END AS engagement_range,
  COUNT(*) AS tweet_count,
  ROUND(CAST(COUNT(*) AS DOUBLE) / SUM(COUNT(*)) OVER() * 100, 2) AS percentage
FROM twitter_lakehouse.processed
GROUP BY 
  CASE
    WHEN (like_count + retweet_count + reply_count + quote_count) = 0 THEN 'No Engagement'
    WHEN (like_count + retweet_count + reply_count + quote_count) BETWEEN 1 AND 100 THEN '1-100'
    WHEN (like_count + retweet_count + reply_count + quote_count) BETWEEN 101 AND 1000 THEN '101-1K'
    WHEN (like_count + retweet_count + reply_count + quote_count) BETWEEN 1001 AND 10000 THEN '1K-10K'
    WHEN (like_count + retweet_count + reply_count + quote_count) BETWEEN 10001 AND 100000 THEN '10K-100K'
    ELSE '100K+'
  END;

-- ============================================================================
-- QUERY 1: Tweet Volume Over Time (for line chart)
-- ============================================================================

SELECT
  SUBSTR(created_at, 1, 10) AS tweet_date,
  COUNT(*) AS tweet_count
FROM twitter_lakehouse.processed
GROUP BY SUBSTR(created_at, 1, 10)
ORDER BY tweet_date DESC;

-- ============================================================================
-- QUERY 2: Average Engagement by Language
-- ============================================================================

SELECT
  lang,
  COUNT(*) AS tweet_count,
  ROUND(AVG(CAST(like_count AS DOUBLE)), 0) AS avg_likes,
  ROUND(AVG(CAST(retweet_count AS DOUBLE)), 0) AS avg_retweets,
  ROUND(AVG(CAST(reply_count AS DOUBLE)), 0) AS avg_replies,
  ROUND(AVG(CAST(quote_count AS DOUBLE)), 0) AS avg_quotes
FROM twitter_lakehouse.processed
GROUP BY lang
ORDER BY tweet_count DESC;

-- ============================================================================
-- QUERY 3: Top Engaging Tweets (Top 100)
-- ============================================================================

SELECT
  tweet_id,
  username,
  text,
  created_at,
  like_count,
  retweet_count,
  reply_count,
  quote_count,
  (like_count + retweet_count + reply_count + quote_count) AS total_engagement
FROM twitter_lakehouse.processed
ORDER BY total_engagement DESC
LIMIT 100;

-- ============================================================================
-- QUERY 4: Real-time Dashboard Data (Last 24 hours)
-- ============================================================================

SELECT
  SUBSTR(created_at, 1, 10) AS tweet_date,
  SUBSTR(created_at, 12, 5) AS time_hour,
  lang,
  COUNT(*) AS tweet_count,
  SUM(like_count) AS total_likes,
  SUM(retweet_count) AS total_retweets
FROM twitter_lakehouse.processed
WHERE from_iso8601_timestamp(created_at) >= (
  SELECT max(from_iso8601_timestamp(created_at)) - INTERVAL '24' HOUR 
  FROM twitter_lakehouse.processed
)
GROUP BY
  SUBSTR(created_at, 1, 10),
  SUBSTR(created_at, 12, 5),
  lang
ORDER BY tweet_date DESC, time_hour DESC;

-- ============================================================================
-- QUERY 5: Hashtag Co-occurrence (Tags that appear together)
-- ============================================================================

SELECT
  hashtags,
  COUNT(*) AS occurrences,
  ROUND(AVG(CAST(like_count AS DOUBLE)), 0) AS avg_likes
FROM twitter_lakehouse.processed
WHERE hashtags IS NOT NULL AND hashtags <> ''
GROUP BY hashtags
ORDER BY occurrences DESC
LIMIT 50;
