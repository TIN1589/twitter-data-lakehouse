# Dashboard Setup Guide

## Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# Install dependencies
pip install requests

# Run dashboard setup script
python app/setup_dashboards.py \
  --host localhost \
  --port 8088 \
  --username admin \
  --password admin
```

This will:
1. Create 5 dashboards
2. Create 11 charts
3. Configure all data sources
4. Add filters and interactions

### Option 2: Manual Setup via Superset UI

Access Superset at `http://localhost:8088`

**Default Credentials:**
- Username: `admin`
- Password: `admin`

---

## Dashboards Overview

### 1. Tweet Volume Trends 📈

**Purpose:** Monitor tweet activity over time

**Charts:**
- **Tweet Count by Date** (Line Chart)
  - Shows daily tweet volume
  - Trend visualization
  - Query: `SELECT date, COUNT(*) FROM tweets GROUP BY date`

- **Hourly Tweet Distribution** (Bar Chart)
  - Hourly breakdown
  - Peak hour identification
  - Query: `SELECT hour, COUNT(*) FROM tweets GROUP BY hour`

**Usage:**
- Identify peak activity times
- Spot unusual spikes or drops
- Monitor pipeline health

---

### 2. Engagement Metrics 💬

**Purpose:** Analyze tweet engagement patterns

**Charts:**
- **Average Engagement by Language** (Bar Chart)
  - Avg likes, retweets, replies per language
  - Compare language performance
  - Query: Shows top languages by engagement

- **Top 20 Engaging Tweets** (Table)
  - Highest performing tweets
  - Clickable for details
  - Shows total_engagement = likes + retweets + replies + quotes

**Usage:**
- Identify high-performing content
- Language preferences for engagement
- Benchmark against historical data

---

### 3. Language Distribution 🌍

**Purpose:** Understand geographic/language diversity

**Charts:**
- **Tweets by Language** (Pie Chart)
  - Language split
  - Percentage breakdown
  - Query: `SELECT lang, COUNT(*) FROM tweets GROUP BY lang`

- **Language Trends Over Time** (Line Chart)
  - Language distribution changes
  - Multiple lines (one per language)
  - Trend over 30 days

**Usage:**
- Market analysis by language
- Content localization strategy
- Audience demographics

---

### 4. Hashtag Analytics 🏷️

**Purpose:** Track trending and high-impact hashtags

**Charts:**
- **Top 50 Hashtags** (Bar Chart)
  - Most used hashtags
  - Average engagement per hashtag
  - Query: `SELECT hashtag, COUNT(*), AVG(engagement) FROM tweets GROUP BY hashtag LIMIT 50`

- **Hashtag Engagement** (Scatter Plot)
  - X-axis: Tweet count using hashtag
  - Y-axis: Total engagement
  - Bubble size: Average engagement
  - Query: Shows correlation between usage and engagement

**Usage:**
- Identify trending hashtags
- Find optimal hashtags for reach
- Track hashtag campaign performance

---

### 5. User Activity 👥

**Purpose:** Analyze user behavior and influence

**Charts:**
- **Top 50 Users by Engagement** (Table)
  - Username, tweet count, total engagement
  - Sortable columns
  - Query: User rankings by influence

- **User Tweet Frequency** (Stat Card)
  - Unique users count
  - Total tweets count
  - Average tweets per user

**Usage:**
- Identify key influencers
- Track user contribution
- Monitor most active users

---

## Creating Custom Dashboards

### Step 1: Create a Dataset

1. Go to **Data** → **Datasets**
2. Click **+ Dataset**
3. Select **Drill** database
4. Enter SQL query:
   ```sql
   SELECT
     SUBSTR(created_at, 1, 10) AS date,
     lang,
     COUNT(*) AS tweet_count
   FROM s3.root.`tweets/*/*.parquet`
   GROUP BY SUBSTR(created_at, 1, 10), lang
   ```
5. Click **Create Dataset**

### Step 2: Create a Chart

1. Click **Charts** in top menu
2. Click **+ Chart**
3. Select your dataset
4. Choose visualization type:
   - **Line**: Time series trends
   - **Bar**: Category comparisons
   - **Pie**: Proportions
   - **Table**: Detailed data
   - **Scatter**: Correlations
   - **Stat**: Single numbers (KPIs)

### Step 3: Configure Chart

1. **Data** tab:
   - Set X-axis, Y-axis, grouping columns
   - Apply filters
   - Set sorting

2. **Customize** tab:
   - Add title and description
   - Set colors and styles
   - Configure axis labels

3. **Advanced** tab:
   - Set cache timeout
   - Add custom SQL filters
   - Configure interactions

### Step 4: Add to Dashboard

1. Click **Save Chart**
2. Select **Add to Dashboard**
3. Choose existing dashboard or create new
4. Click **Save**

---

## Adding Filters to Dashboards

### Global Filters (Dashboard-wide)

1. Go to Dashboard
2. Click **Edit Dashboard**
3. Click **+ Add Filter**
4. Select filter type:
   - **Date**: Filter by date range
   - **String**: Filter by text value
   - **Numeric**: Filter by number range
   - **Select**: Dropdown selection

**Example: Date Range Filter**
```
Name: Date Range
Type: Date
Column: created_at
Default: Last 30 days
Operators: >= and <=
```

### Chart-level Filters

1. Open chart in edit mode
2. In **Data** tab, click **+ Add Filter**
3. Select column and condition:
   - `lang = 'en'`
   - `like_count > 100`
   - `created_at BETWEEN '2026-06-01' AND '2026-06-30'`

---

## Enabling Drill-Downs (Interactive)

### From Chart to Details

1. Enable drill-through on a chart:
   - Edit chart
   - Go to **Interactions** tab
   - Set "Click behavior" to drill-down

2. Configure drill-down target:
   - Select target dashboard or chart
   - Map source columns to target filters

**Example:**
- Click on hashtag in "Top Hashtags" chart
- Drill down to "Engagement Metrics" dashboard filtered by that hashtag

---

## Performance Tips for Dashboards

### 1. Use Pre-computed Views

```sql
-- SLOW: Computed on every load
SELECT hashtags, COUNT(*) as cnt
FROM s3.root.`tweets/*/*.parquet`
GROUP BY hashtags
LIMIT 50

-- FAST: Pre-computed, cached
SELECT * FROM hashtag_performance
WHERE date BETWEEN NOW() - 30 DAYS AND NOW()
LIMIT 50
```

### 2. Set Appropriate Cache TTL

- **KPI Metrics**: 1 hour cache (updates hourly)
- **Trends**: 30 minutes cache
- **Raw data**: 5 minutes cache (near real-time)

To set cache:
1. Edit chart
2. Go to **Advanced** tab
3. Set "Cache Timeout" (seconds)

### 3. Use Date Filters

Always filter by date range on dashboards:
```sql
WHERE created_at >= DATE_SUB(CURDATE(), 30)
```

This activates partition pruning in Drill → 50-100x faster!

### 4. Limit Result Sets

```sql
-- Include LIMIT in every query
SELECT TOP 100 ...
LIMIT 100
```

---

## Connecting to Different Data Sources

### Currently Configured

- **Drill** (primary)
  - Connection: `drill+sadrill://drill:8047/dfs/s3.root`
  - Database: `s3.root`
  - Tables: Parquet files in MinIO

### Adding Additional Databases

1. Go to **Data** → **Databases**
2. Click **+ Database**
3. Select database type:
   - PostgreSQL
   - MySQL
   - Elasticsearch
   - etc.
4. Enter connection details
5. Click **Test Connection**
6. Click **Create Database**

---

## Exporting Dashboards

### Export as JSON

1. Open dashboard
2. Click **...** (menu)
3. Select **Export as JSON**
4. Save file

### Export as PDF

1. Open dashboard
2. Click **Print**
3. Save as PDF

### Share Dashboard

1. Click **Share** button (top right)
2. Generate shareable link
3. Configure access permissions:
   - Public (anyone)
   - Private (only me)
   - Shared users (specific people)

---

## Troubleshooting

### Dashboard is Loading Slowly

1. Check number of charts (reduce to < 5 per dashboard)
2. Verify Drill is responsive: `SELECT COUNT(*) FROM s3.root.`tweets/*/*.parquet``
3. Check partition filters are working
4. Enable caching on charts

### Chart Shows No Data

1. Verify Drill database connection is active
2. Check dataset query runs in Drill directly
3. Verify data exists in MinIO: `aws s3 ls s3://twitter-data/tweets/`
4. Check date range filters

### Drill Connection Error

1. Verify Drill container is running: `docker-compose ps drill`
2. Test Drill UI: http://localhost:8047
3. Check MinIO connection: `docker-compose logs drill` for errors
4. Verify S3 credentials in Drill config

### Out of Memory Error

1. Reduce number of charts per dashboard
2. Add date filters to limit data scanned
3. Reduce cache TTL
4. Increase Drill heap size in docker-compose.yaml

---

## Advanced: Custom Charts & Plugins

### Creating a Custom Metric

1. Create SQL dataset:
```sql
SELECT
  SUBSTR(created_at, 1, 10) AS date,
  SUM(like_count) AS daily_likes
FROM s3.root.`tweets/*/*.parquet`
GROUP BY SUBSTR(created_at, 1, 10)
```

2. Create a **Stat** chart:
   - Selects: `daily_likes`
   - Shows: Single number (today's total likes)

### Creating a Custom Alert

1. Edit dashboard
2. Set threshold alert on chart:
   - "Alert if tweet_count < 10 per hour"
   - Email notification to admin@domain.com

---

## Best Practices

✓ **DO:**
- Group related metrics on single dashboard
- Use consistent color schemes
- Add descriptive titles and descriptions
- Cache frequently-accessed queries
- Update dashboards monthly

✗ **DON'T:**
- Put 20+ charts on one dashboard (too slow)
- Query all historical data without date filters
- Use SELECT * without LIMIT
- Trust uncached real-time data for reporting
- Forget to test drill-down links

---

## Summary

**Quick Checklist:**
- [ ] Verify Drill connection in Superset
- [ ] Create datasets from drill_queries.sql
- [ ] Create 5 main dashboards (or run setup_dashboards.py)
- [ ] Add date range filters to each dashboard
- [ ] Set appropriate cache timeouts
- [ ] Test drill-down interactions
- [ ] Share dashboards with team

**Next Steps:**
- Monitor dashboard usage
- Adjust queries based on performance
- Add custom charts for specific business questions
- Integrate with Slack/email for alerts
