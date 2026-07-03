-- Drill SQL queries for Twitter data analytics
-- These queries are optimized for the data structure stored in MinIO
-- Run these on Drill UI or via sqlalchemy-drill from Superset

-- ============================================================================
-- SETUP: Create workspace for materialized views (if needed)
-- ============================================================================

-- Note: Materialized views in Drill are typically created via Hive metastore
-- For now, we create views that Superset can query directly

-- ============================================================================
-- VIEW 1: Daily Tweet Summary
-- Purpose: Pre-aggregated daily stats for fast dashboard queries
-- ============================================================================

CREATE VIEW daily_tweet_summary AS
SELECT
  SUBSTR(created_at, 1, 10) AS tweet_date,
  lang,
  COUNT(*) AS total_tweets,
  SUM(CAST(like_count AS DECIMAL(15,2))) AS total_likes,
  SUM(CAST(retweet_count AS DECIMAL(15,2))) AS total_retweets,
  SUM(CAST(reply_count AS DECIMAL(15,2))) AS total_replies,
  SUM(CAST(quote_count AS DECIMAL(15,2))) AS total_quotes,
  SUM(CAST(like_count + retweet_count + reply_count + quote_count AS DECIMAL(15,2))) AS total_engagement,
  ROUND(AVG(CAST(like_count AS DECIMAL(15,2))), 2) AS avg_likes,
  ROUND(AVG(CAST(retweet_count AS DECIMAL(15,2))), 2) AS avg_retweets,
  ROUND(AVG(CAST(reply_count AS DECIMAL(15,2))), 2) AS avg_replies,
  ROUND(AVG(CAST(quote_count AS DECIMAL(15,2))), 2) AS avg_quotes,
  MAX(CAST(like_count AS DECIMAL(15,2))) AS max_likes,
  MAX(CAST(retweet_count AS DECIMAL(15,2))) AS max_retweets
FROM s3.root.`tweets/*/*/*/*.parquet`
GROUP BY SUBSTR(created_at, 1, 10), lang
ORDER BY tweet_date DESC;

-- ============================================================================
-- VIEW 2: Top Hashtags by Engagement
-- Purpose: Quick lookup for trending hashtags
-- ============================================================================

CREATE VIEW hashtag_performance AS
SELECT
  hashtags,
  COUNT(*) AS tweet_count,
  SUM(CAST(like_count AS DECIMAL(15,2))) AS total_likes,
  SUM(CAST(like_count + retweet_count + reply_count + quote_count AS DECIMAL(15,2))) AS total_engagement,
  ROUND(AVG(CAST(like_count AS DECIMAL(15,2))), 2) AS avg_likes
FROM s3.root.`tweets/*/*/*/*.parquet`
WHERE hashtags IS NOT NULL AND hashtags <> ''
GROUP BY hashtags
ORDER BY total_engagement DESC
LIMIT 100;

-- ============================================================================
-- VIEW 3: User Performance Rankings
-- Purpose: Top users by engagement
-- ============================================================================

CREATE VIEW user_performance AS
SELECT
  username,
  user_id,
  COUNT(*) AS tweet_count,
  SUM(CAST(like_count AS DECIMAL(15,2))) AS total_likes,
  SUM(CAST(retweet_count AS DECIMAL(15,2))) AS total_retweets,
  SUM(CAST(like_count + retweet_count + reply_count + quote_count AS DECIMAL(15,2))) AS total_engagement,
  ROUND(AVG(CAST(like_count AS DECIMAL(15,2))), 2) AS avg_likes,
  MAX(CAST(created_at, 1, 10)) AS last_tweet_date
FROM s3.root.`tweets/*/*/*/*.parquet`
GROUP BY username, user_id
ORDER BY total_engagement DESC
LIMIT 100;

-- ============================================================================
-- VIEW 4: Language Distribution Trends
-- Purpose: See how tweet distribution changes by language over time
-- ============================================================================

CREATE VIEW language_trends AS
SELECT
  SUBSTR(created_at, 1, 10) AS tweet_date,
  lang,
  COUNT(*) AS tweet_count,
  SUM(CAST(like_count + retweet_count + reply_count + quote_count AS DECIMAL(15,2))) AS total_engagement
FROM s3.root.`tweets/*/*/*/*.parquet`
GROUP BY SUBSTR(created_at, 1, 10), lang
ORDER BY tweet_date DESC, total_engagement DESC;

-- ============================================================================
-- VIEW 5: Engagement Metrics Distribution
-- Purpose: Understand engagement patterns (percentiles, ranges)
-- ============================================================================

CREATE VIEW engagement_distribution AS
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
  ROUND(CAST(COUNT(*) AS DECIMAL(15,2)) / SUM(COUNT(*)) OVER() * 100, 2) AS percentage
FROM s3.root.`tweets/*/*/*/*.parquet`
GROUP BY engagement_range
ORDER BY 
  CASE
    WHEN engagement_range = 'No Engagement' THEN 0
    WHEN engagement_range = '1-100' THEN 1
    WHEN engagement_range = '101-1K' THEN 2
    WHEN engagement_range = '1K-10K' THEN 3
    WHEN engagement_range = '10K-100K' THEN 4
    ELSE 5
  END;

-- ============================================================================
-- QUERY 1: Tweet Volume Over Time (for line chart)
-- ============================================================================

SELECT
  SUBSTR(created_at, 1, 10) AS tweet_date,
  COUNT(*) AS tweet_count
FROM s3.root.`tweets/*/*/*/*.parquet`
GROUP BY SUBSTR(created_at, 1, 10)
ORDER BY tweet_date DESC;

-- ============================================================================
-- QUERY 2: Average Engagement by Language
-- ============================================================================

SELECT
  lang,
  COUNT(*) AS tweet_count,
  ROUND(AVG(CAST(like_count AS DECIMAL(15,2))), 0) AS avg_likes,
  ROUND(AVG(CAST(retweet_count AS DECIMAL(15,2))), 0) AS avg_retweets,
  ROUND(AVG(CAST(reply_count AS DECIMAL(15,2))), 0) AS avg_replies,
  ROUND(AVG(CAST(quote_count AS DECIMAL(15,2))), 0) AS avg_quotes
FROM s3.root.`tweets/*/*/*/*.parquet`
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
FROM s3.root.`tweets/*/*/*/*.parquet`
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
  SUM(CAST(like_count AS DECIMAL(15,2))) AS total_likes,
  SUM(CAST(retweet_count AS DECIMAL(15,2))) AS total_retweets
FROM s3.root.`tweets/*/*/*/*.parquet`
WHERE created_at >= (SELECT MAX(created_at) FROM s3.root.`tweets/*/*/*/*.parquet`)[1] - INTERVAL '24' HOUR
GROUP BY
  SUBSTR(created_at, 1, 10),
  SUBSTR(created_at, 12, 5),
  lang
ORDER BY tweet_date DESC, time_hour DESC;

-- ============================================================================
-- QUERY 5: Hashtag Co-occurrence (Tags that appear together)
-- ============================================================================

-- This is a simplified version; full co-occurrence would require more complex logic
SELECT
  hashtags,
  COUNT(*) AS occurrences,
  ROUND(AVG(CAST(like_count AS DECIMAL(15,2))), 0) AS avg_likes
FROM s3.root.`tweets/*/*/*/*.parquet`
WHERE hashtags IS NOT NULL AND hashtags <> ''
GROUP BY hashtags
ORDER BY occurrences DESC
LIMIT 50;

-- ============================================================================
-- OPTIMIZATION NOTES
-- ============================================================================
-- 
-- 1. PARTITIONING: Data is stored in tweets/YYYY/MM/DD/ structure
--    - Queries automatically use partition pruning
--    - WHERE clauses on date improve query performance
--
-- 2. FILE FORMAT: Parquet with snappy compression
--    - Column-oriented storage = faster aggregations
--    - Compression reduces storage and I/O
--
-- 3. INDEXING: Drill doesn't use traditional indexes
--    - Instead, use WHERE clauses and LIMIT to reduce data scanned
--    - Group by low-cardinality columns (lang, user_id)
--
-- 4. CACHING: Enable in Drill web UI settings
--    - Results cache reduces repeated query times
--    - Best for frequently used views
--
-- 5. PERFORMANCE TUNING:
--    - Use CAST() for type safety
--    - Use SUBSTRING/SUBSTR for date extraction
--    - Avoid SELECT * - specify needed columns
--    - Use GROUP BY on indexed fields first
--
-- ============================================================================
