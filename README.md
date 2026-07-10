# Twitter Data Lakehouse — AWS Cloud Architecture

Data Lakehouse pipeline phân tích dữ liệu Twitter (mock data), triển khai trên **AWS Cloud**.

## Kiến trúc hệ thống

```
Twitter Mock Data (20 tweets/batch)
         │
         ▼ [1. Generate & Validate]
┌─────────────────────────────────┐
│       Amazon EC2 t3.micro       │
│   ┌─────────────────────────┐   │
│   │    Apache Airflow :8080  │   │  ← Pipeline Orchestration
│   │    DAG: twitter_etl      │   │  ← Schedule: mỗi 6 tiếng
│   └───────────┬─────────────┘   │
│               │                 │
│   ┌───────────▼─────────────┐   │
│   │  PostgreSQL :5433        │   │  ← Airflow Metadata DB
│   └─────────────────────────┘   │
└───────────────┬─────────────────┘
                │ [2. Upload boto3]
                ▼
┌───────────────────────────────────────────┐
│             AWS Cloud Services            │
│                                           │
│  ┌──────────────────────────────────────┐ │
│  │         Amazon S3                    │ │  ← Data Lake Storage
│  │  bucket: twitter-data-lakehouse      │ │
│  │  tweets/*.parquet  (Athena queries)  │ │
│  │  tweets-raw/*.json (raw backup)      │ │
│  └──────────────┬───────────────────────┘ │
│                 │ [3. Schema catalog]      │
│  ┌──────────────▼───────────────────────┐ │
│  │       AWS Glue Data Catalog          │ │  ← Metadata Store
│  │  database: twitter_lakehouse         │ │
│  │  table: tweets (13 columns)          │ │
│  └──────────────┬───────────────────────┘ │
│                 │ [4. SQL query]           │
│  ┌──────────────▼───────────────────────┐ │
│  │         Amazon Athena                │ │  ← Serverless SQL Engine
│  │  workgroup: twitter-lakehouse        │ │
│  │  results → S3 athena-results bucket  │ │
│  └──────────────┬───────────────────────┘ │
└─────────────────┼─────────────────────────┘
                  │ [5. Visualize]
                  ▼
┌─────────────────────────────────┐
│       Amazon EC2 t3.micro       │
│   ┌─────────────────────────┐   │
│   │  Apache Superset :8088   │   │  ← BI Dashboard
│   │  Connected to Athena     │   │
│   └─────────────────────────┘   │
└─────────────────────────────────┘
```

## AWS Services sử dụng

| Service | Vai trò | Chi phí/tháng |
|---------|---------|---------------|
| **Amazon EC2** t3.micro | Host Airflow + Superset | ~$0 (free tier) |
| **Amazon S3** | Data Lake — lưu Parquet + JSON | ~$0.02 |
| **AWS Glue Data Catalog** | Metadata store — quản lý schema | $0 (free tier) |
| **Amazon Athena** | Serverless SQL query engine | ~$0.01 (pay-per-query) |
| **Tổng** | | **~$0.03/tháng** |

## Phân công vai trò nhóm

| Vai trò | Thành viên | Phần phụ trách |
|---------|-----------|----------------|
| Cloud Infra & DevOps | Vinh, Tín | EC2, Docker, Airflow, PostgreSQL |
| Cloud Storage | Vinh, Tín | Amazon S3, ETL pipeline, boto3 upload |
| Cloud Compute | Hoàng, Triệu | AWS Glue Catalog, Amazon Athena |
| Cloud BI & Visualization | Hoàng, Triệu | Apache Superset, Dashboard, Charts |

## Pipeline Flow

1. **Airflow DAG** (`twitter_etl`) chạy mỗi 6 giờ hoặc trigger thủ công
2. **generate_twitter_data** — sinh 20 mock tweets từ nhiều user profiles
3. **validate_twitter_data** — kiểm tra chất lượng bằng Pydantic (yêu cầu ≥80% valid)
4. **clean_twitter_data** — flatten nested data, thêm batch metadata
5. **upload_to_s3** — upload **Parquet** (analytics) + **JSON** (backup) lên Amazon S3 bằng `boto3`
6. **aggregate_daily_stats** — tổng hợp thống kê ngày
7. **cleanup_old_data** — xoá dữ liệu cũ hơn 30 ngày
8. **log_pipeline_metrics** — báo cáo metrics pipeline

## Cài đặt và chạy

### Yêu cầu

- **AWS Account** với quyền S3, Glue, Athena
- **Amazon EC2** t3.micro (1GB RAM + 4GB Swap), Ubuntu 22.04
- **Docker** + **Docker Compose** v2
- Security Group mở ports: `8080` (Airflow), `8088` (Superset)

### Setup EC2

```bash
git clone https://github.com/TIN1589/twitter-data-lakehouse.git
cd twitter-data-lakehouse

# Copy và điền thông tin AWS credentials
cp sample.env .env
nano .env

# Build và start
docker compose build
docker compose up -d
```

### Biến môi trường cần thiết (`.env`)

```bash
# AWS S3 — Data Lake thực
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=ap-southeast-1
S3_BUCKET_NAME=twitter-data-lakehouse

# PostgreSQL — Airflow Metadata
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow

# Superset
SUPERSET_SECRET_KEY=your_secret_key
```

### Setup AWS Resources (chỉ cần làm 1 lần)

```python
import boto3

# 1. Tạo S3 bucket
s3 = boto3.client('s3', region_name='ap-southeast-1')
s3.create_bucket(
    Bucket='twitter-data-lakehouse',
    CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
)

# 2. Tạo Glue database và table (xem scripts/setup_aws.py)
# 3. Tạo Athena workgroup với S3 output location
```

## Truy cập Services

| Service | URL | Login |
|---------|-----|-------|
| **Airflow** | `http://<EC2-IP>:8080` | admin / admin |
| **Superset** | `http://<EC2-IP>:8088` | admin / admin |
| **AWS S3** | https://s3.console.aws.amazon.com/s3/buckets/twitter-data-lakehouse | AWS Console |
| **AWS Athena** | https://ap-southeast-1.console.aws.amazon.com/athena | workgroup: twitter-lakehouse |

> ⚠️ **Lưu ý Athena**: Chọn đúng **workgroup `twitter-lakehouse`** và **database `twitter_lakehouse`** trước khi query.

## Query mẫu trên Amazon Athena

```sql
-- Thống kê tweets theo username
SELECT
    username,
    COUNT(*) AS total_tweets,
    ROUND(AVG(like_count), 0) AS avg_likes,
    MAX(retweet_count) AS max_retweets
FROM tweets
GROUP BY username
ORDER BY total_tweets DESC;

-- Top hashtags
SELECT hashtags, COUNT(*) AS frequency
FROM tweets
WHERE hashtags != ''
GROUP BY hashtags
ORDER BY frequency DESC
LIMIT 10;

-- Tổng engagement
SELECT
    username,
    SUM(like_count + retweet_count) AS total_engagement
FROM tweets
GROUP BY username
ORDER BY total_engagement DESC;
```

## Cấu trúc Project

```
├── app/
│   └── dags/
│       ├── twitter_etl.py          # Airflow DAG — main pipeline (7 tasks)
│       ├── mock_twitter_data.py    # Mock data generator
│       ├── models.py               # Pydantic validation models
│       ├── data_quality.py         # Data quality checker
│       └── pipeline_utils.py       # Aggregation & cleanup utilities
├── conf/
│   └── airflow/
│       └── webserver_config.py     # Airflow webserver config (CSRF fix)
├── docs/
│   └── architecture.md             # Chi tiết kiến trúc & Lakehouse concept
├── scripts/
│   ├── init.sh                     # EC2 setup script
│   └── health-check.sh             # Health monitoring
├── .github/
│   └── workflows/
│       └── ci-cd.yml               # GitHub Actions CI/CD
├── docker-compose.yaml             # Services: Airflow, Superset, PostgreSQL
├── airflow.Dockerfile              # Custom Airflow image (boto3, pydantic, pyarrow)
├── superset_drill.Dockerfile       # Superset + PyAthena connector
├── sample.env                      # Environment template
└── README.md
```

## Tại sao Data Lakehouse?

| | Data Lake | Data Warehouse | **Data Lakehouse (Dự án này)** |
|---|---|---|---|
| **Storage** | Cheap (S3) | Expensive | **Amazon S3 (Parquet)** |
| **SQL** | Hạn chế | Full | **Amazon Athena (Serverless)** |
| **Schema** | Không có | Rigid | **AWS Glue Catalog (Flexible)** |
| **Chi phí** | Thấp | Cao | **~$0.03/tháng** |
| **Scale** | Petabyte | Giới hạn | **Petabyte (AWS native)** |

## CI/CD

```
Push to main → GitHub Actions → Lint (flake8 + yamllint) → Deploy to EC2 (SSH)
```

Xem: [.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml)

## Troubleshooting

```bash
# Kiểm tra containers
docker compose ps
docker compose logs <service-name>

# Kiểm tra RAM
free -m
docker stats --no-stream

# Restart service
docker compose restart <service-name>
```

| Lỗi | Nguyên nhân | Cách sửa |
|-----|-------------|----------|
| Superset trắng màn hình | Session cũ | Mở tab ẩn danh, F5 |
| Athena "No output location" | Sai workgroup | Đổi sang `twitter-lakehouse` |
| DAG không trigger | CSRF | Đăng xuất → đăng nhập lại |

## License

MIT License — see [LICENSE](LICENSE) for details.
