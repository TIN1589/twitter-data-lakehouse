#!/usr/bin/env python
"""
Superset Dashboard Setup Script

This script helps set up all dashboards for the Twitter Data Lakehouse.
It uses the Superset API to create datasets, charts, and dashboards.

Prerequisites:
- Superset running on http://localhost:8088
- Drill database connection already configured
- Admin user logged in

Usage:
    python setup_dashboards.py --host localhost --port 8088 --username admin --password admin
"""

import json
import sys
import time
from typing import Dict, List, Optional

import requests


class SupersetClient:
    """Client for Superset API operations."""

    def __init__(self, host: str, port: int, username: str, password: str):
        """Initialize Superset client."""
        self.base_url = f"http://{host}:{port}/api/v1"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.csrf_token = None
        self.login()

    def login(self):
        """Authenticate with Superset."""
        login_url = f"{self.base_url.replace('/api/v1', '')}/api/v1/security/login"
        
        payload = {
            "username": self.username,
            "password": self.password,
            "provider": "db",
            "refresh": True,
        }
        
        try:
            response = self.session.post(login_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if "access_token" in data:
                self.session.headers.update({
                    "Authorization": f"Bearer {data['access_token']}",
                    "Content-Type": "application/json",
                })
                print("[OK] Logged into Superset")
            else:
                print("[ERROR] Login failed - no access token")
                sys.exit(1)
                
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Login failed: {e}")
            sys.exit(1)

    def get_databases(self) -> List[Dict]:
        """Get list of available databases."""
        try:
            response = self.session.get(f"{self.base_url}/database/")
            response.raise_for_status()
            return response.json().get("result", [])
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to get databases: {e}")
            return []

    def get_database_id(self, db_name: str = "Drill") -> Optional[int]:
        """Get database ID by name."""
        databases = self.get_databases()
        for db in databases:
            if db.get("database_name") == db_name:
                return db.get("id")
        return None

    def create_database(self, name: str, sqlalchemy_uri: str) -> Optional[int]:
        """Create a new database connection."""
        payload = {
            "database_name": name,
            "sqlalchemy_uri": sqlalchemy_uri,
        }
        try:
            response = self.session.post(f"{self.base_url}/database/", json=payload)
            response.raise_for_status()
            db_id = response.json().get("id")
            print(f"[OK] Created database connection: {name}")
            return db_id
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to create database connection {name}: {e}")
            try:
                print(f"Response details: {response.text}")
            except:
                pass
            return None

    def create_dataset(self, name: str, sql: str, db_id: int) -> Optional[Dict]:
        """Create a new SQL dataset."""
        payload = {
            "database": db_id,
            "schema": "dfs",
            "table_name": name,
            "sql": sql,
        }
        
        try:
            response = self.session.post(f"{self.base_url}/dataset/", json=payload)
            response.raise_for_status()
            result = response.json()
            print(f"[OK] Created dataset: {name}")
            return result
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to create dataset {name}: {e}")
            return None

    def create_chart(
        self,
        name: str,
        dataset_id: int,
        viz_type: str,
        query_dict: Dict,
    ) -> Optional[Dict]:
        """Create a new chart."""
        payload = {
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "slice_name": name,
            "viz_type": viz_type,
            "params": json.dumps(query_dict),
        }
        
        try:
            response = self.session.post(f"{self.base_url}/chart/", json=payload)
            response.raise_for_status()
            result = response.json()
            print(f"[OK] Created chart: {name}")
            return result
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to create chart {name}: {e}")
            return None

    def create_dashboard(
        self,
        name: str,
        description: str,
        charts: List[int],
    ) -> Optional[Dict]:
        """Create a new dashboard."""
        payload = {
            "dashboard_title": name,
            "description": description,
            "slices": charts,
        }
        
        try:
            response = self.session.post(f"{self.base_url}/dashboard/", json=payload)
            response.raise_for_status()
            result = response.json().get("result", {})
            print(f"[OK] Created dashboard: {name}")
            return result
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to create dashboard {name}: {e}")
            return None


# ============================================================================
# DASHBOARD DEFINITIONS
# ============================================================================

DASHBOARDS_CONFIG = {
    "Tweet Volume Trends": {
        "description": "Tweet volume over time with daily breakdowns",
        "charts": [
            {
                "name": "Tweet Count by Date",
                "sql": """
                    SELECT
                        SUBSTR(created_at, 1, 10) AS tweet_date,
                        COUNT(*) AS tweet_count
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    GROUP BY SUBSTR(created_at, 1, 10)
                    ORDER BY tweet_date DESC
                """,
                "viz_type": "line",
            },
            {
                "name": "Hourly Tweet Distribution",
                "sql": """
                    SELECT
                        SUBSTR(created_at, 1, 13) AS hour,
                        COUNT(*) AS tweet_count
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    GROUP BY SUBSTR(created_at, 1, 13)
                    ORDER BY hour DESC
                """,
                "viz_type": "bar",
            },
        ],
    },
    
    "Engagement Metrics": {
        "description": "Overall engagement metrics and trends",
        "charts": [
            {
                "name": "Average Engagement by Language",
                "sql": """
                    SELECT
                        lang,
                        ROUND(AVG(CAST(like_count AS DECIMAL(15,2))), 0) AS avg_likes,
                        ROUND(AVG(CAST(retweet_count AS DECIMAL(15,2))), 0) AS avg_retweets,
                        ROUND(AVG(CAST(reply_count AS DECIMAL(15,2))), 0) AS avg_replies,
                        COUNT(*) AS tweet_count
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    GROUP BY lang
                    ORDER BY tweet_count DESC
                """,
                "viz_type": "bar",
            },
            {
                "name": "Top 20 Engaging Tweets",
                "sql": """
                    SELECT
                        username,
                        text,
                        like_count,
                        retweet_count,
                        reply_count,
                        quote_count,
                        (like_count + retweet_count + reply_count + quote_count) AS total_engagement
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    ORDER BY total_engagement DESC
                    LIMIT 20
                """,
                "viz_type": "table",
            },
        ],
    },
    
    "Language Distribution": {
        "description": "Tweet distribution by language and language trends",
        "charts": [
            {
                "name": "Tweets by Language",
                "sql": """
                    SELECT
                        lang,
                        COUNT(*) AS tweet_count
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    GROUP BY lang
                    ORDER BY tweet_count DESC
                """,
                "viz_type": "pie",
            },
            {
                "name": "Language Trends Over Time",
                "sql": """
                    SELECT
                        SUBSTR(created_at, 1, 10) AS tweet_date,
                        lang,
                        COUNT(*) AS tweet_count
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    GROUP BY SUBSTR(created_at, 1, 10), lang
                    ORDER BY tweet_date DESC, tweet_count DESC
                """,
                "viz_type": "line",
            },
        ],
    },
    
    "Hashtag Analytics": {
        "description": "Hashtag performance and trending tags",
        "charts": [
            {
                "name": "Top 50 Hashtags",
                "sql": """
                    SELECT
                        hashtags,
                        COUNT(*) AS occurrences,
                        ROUND(AVG(CAST(like_count AS DECIMAL(15,2))), 0) AS avg_likes
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    WHERE hashtags IS NOT NULL AND hashtags <> ''
                    GROUP BY hashtags
                    ORDER BY occurrences DESC
                    LIMIT 50
                """,
                "viz_type": "bar",
            },
            {
                "name": "Hashtag Engagement",
                "sql": """
                    SELECT
                        hashtags,
                        COUNT(*) AS tweet_count,
                        SUM(CAST(like_count + retweet_count + reply_count + quote_count AS DECIMAL(15,2))) AS total_engagement,
                        ROUND(AVG(CAST(like_count + retweet_count + reply_count + quote_count AS DECIMAL(15,2))), 0) AS avg_engagement
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    WHERE hashtags IS NOT NULL AND hashtags <> ''
                    GROUP BY hashtags
                    ORDER BY total_engagement DESC
                    LIMIT 30
                """,
                "viz_type": "scatter",
            },
        ],
    },
    
    "User Activity": {
        "description": "Top users and user engagement patterns",
        "charts": [
            {
                "name": "Top 50 Users by Engagement",
                "sql": """
                    SELECT
                        username,
                        COUNT(*) AS tweet_count,
                        SUM(CAST(like_count + retweet_count + reply_count + quote_count AS DECIMAL(15,2))) AS total_engagement,
                        ROUND(AVG(CAST(like_count + retweet_count + reply_count + quote_count AS DECIMAL(15,2))), 0) AS avg_engagement
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                    GROUP BY username
                    ORDER BY total_engagement DESC
                    LIMIT 50
                """,
                "viz_type": "table",
            },
            {
                "name": "User Tweet Frequency",
                "sql": """
                    SELECT
                        COUNT(DISTINCT username) AS unique_users,
                        COUNT(*) AS total_tweets
                    FROM s3.root.`tweets/*/*/*/*.parquet`
                """,
                "viz_type": "stat",
            },
        ],
    },
}


def setup_dashboards(host: str, port: int, username: str, password: str):
    """Set up all dashboards in Superset."""
    client = SupersetClient(host, port, username, password)
    
    # Get Drill database ID
    db_id = client.get_database_id("Drill")
    if not db_id:
        print("[INFO] Drill database not found. Attempting to create connection automatically...")
        db_id = client.create_database("Drill", "drill+sadrill://drill:8047/dfs/s3.root?use_ssl=False")
        if not db_id:
            print("[ERROR] Could not create Drill database connection. Please configure it manually in Superset UI.")
            sys.exit(1)
    
    print(f"[INFO] Using Drill database ID: {db_id}\n")
    
    # Create each dashboard
    for dashboard_name, config in DASHBOARDS_CONFIG.items():
        print(f"\n[INFO] Setting up dashboard: {dashboard_name}")
        print("-" * 50)
        
        chart_ids = []
        
        # Create charts for this dashboard
        for chart_config in config.get("charts", []):
            chart_name = chart_config["name"]
            sql = chart_config["sql"]
            viz_type = chart_config["viz_type"]
            
            # Create dataset
            dataset = client.create_dataset(f"{chart_name}_dataset", sql, db_id)
            if not dataset:
                continue
            
            dataset_id = dataset.get("id")
            
            # Create chart
            query_dict = {
                "viz_type": viz_type,
                "granularity_sqla": None,
                "time_range": "No filter",
            }
            
            chart = client.create_chart(chart_name, dataset_id, viz_type, query_dict)
            if chart:
                chart_ids.append(chart.get("id"))
                time.sleep(0.5)  # Rate limiting
        
        # Create dashboard
        if chart_ids:
            client.create_dashboard(
                dashboard_name,
                config.get("description", ""),
                chart_ids,
            )
            print(f"[OK] Dashboard '{dashboard_name}' setup complete\n")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Set up Twitter Data Lakehouse dashboards in Superset"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Superset hostname (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8088,
        help="Superset port (default: 8088)",
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Superset username (default: admin)",
    )
    parser.add_argument(
        "--password",
        default="admin",
        help="Superset password (default: admin)",
    )
    
    args = parser.parse_args()
    
    print(f"Setting up Superset dashboards...")
    print(f"  Host: {args.host}:{args.port}")
    print(f"  User: {args.username}\n")
    
    try:
        setup_dashboards(args.host, args.port, args.username, args.password)
        print("\n[SUCCESS] All dashboards created!")
    except KeyboardInterrupt:
        print("\n[INFO] Setup interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
