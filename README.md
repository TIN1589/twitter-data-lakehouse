# Twitter Data Lakehouse — Cloud Deployment

Data Lakehouse pipeline phân tích dữ liệu Twitter (mock data), triển khai trên **AWS EC2**.

> 📖 **Tài liệu kiến trúc chi tiết**: Xem [docs/architecture.md](docs/architecture.md) — bao gồm diagrams, so sánh Lakehouse concept, và đề xuất kiến trúc Production trên AWS.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Airflow    │────▶│    MinIO     │────▶│  Apache Drill │────▶│   Superset   │
│ (Orchestrate)│     │  (S3 Storage)│     │  (SQL Engine) │     │(Visualization│
│  :8080       │     │  :9000/:9090 │     │  :8047        │     │  :8088       │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                    ▲                    │                     │
       │         CSV + JSON + Parquet           │                     │
       └─── Mock Data ──────┘              S3A connector         Drill JDBC
```

### Tại sao Lakehouse?

| | Data Lake | Data Warehouse | **Data Lakehouse** (Dự án này) |
|---|-----------|----------------|-------------------------------|
| **Storage** | Cheap (S3) | Expensive (Redshift) | **Cheap (MinIO/S3)** |
| **Format** | Raw files | Proprietary | **Open (Parquet)** |
| **SQL** | Limited | Full | **Full (Drill)** |
| **Chi phí** | Thấp | Cao | **Thấp** |

> 📖 Chi tiết: [docs/architecture.md → Section 4](docs/architecture.md#4-data-lakehouse--khái-niệm--so-sánh)

**Phân công vai trò:**
| Vai trò | Thành viên | Phần phụ trách |
|---------|-----------|----------------|
| Cloud Infra & DevOps | Vinh, Tín | Docker, Network, Airflow, PostgreSQL |
| Cloud Storage | Vinh, Tín | MinIO, ETL pipeline, Data upload |
| Cloud Compute | Hoàng, Triệu | Apache Drill, SQL queries |
| Cloud BI & Visualization | Hoàng, Triệu | Apache Superset, Charts |

## Prerequisites

- **AWS EC2**: t3.micro (1GB RAM + 4GB Swap), Ubuntu 22.04
- **Docker** + **Docker Compose** (v2)
- Security Group mở ports: 8080, 8088, 8047, 9000, 9090

## Quick Start

### 1. Clone & Setup

```bash
git clone <repo-url> && cd Twitter-Data-Lakehouse

# Setup tự động (cài Docker nếu chưa có, tạo swap, start services)
chmod +x scripts/init.sh
./scripts/init.sh
```

### 2. Manual Setup (nếu không dùng script)

```bash
# Tạo .env
cp sample.env .env

# Tạo thư mục
mkdir -p app/logs data
chmod -R 777 app/logs

# Build & start
docker compose build
docker compose up -d
```

### 3. Truy cập Services

| Service | URL | Login |
|---------|-----|-------|
| Airflow | http://\<EC2-IP\>:8080 | airflow / airflow |
| MinIO Console | http://\<EC2-IP\>:9090 | minioadmin / minioadmin |
| Apache Drill | http://\<EC2-IP\>:8047 | — |
| Superset | http://\<EC2-IP\>:8088 | admin / admin |

## Pipeline Flow

1. **Airflow DAG** (`twitter_etl`) chạy mỗi 6 giờ
2. **Mock Data Generator** tạo 50 tweets giả lập từ 8 user profiles khác nhau
3. **Clean & Transform**: flatten nested data, thêm batch metadata
4. **Upload to MinIO** via `boto3`: **CSV** (readable) + **JSON** (raw backup) + **Parquet** (columnar, fast queries)
5. **Drill** query trực tiếp Parquet/CSV/JSON trên MinIO qua S3A connector
6. **Superset** kết nối Drill để tạo charts và dashboards

### Kết nối Superset → Drill

Trong Superset, thêm database connection:
```
drill+sadrill://drill:8047/dfs/s3.root?use_ssl=False
```

### Query mẫu trên Drill

```sql
-- Thống kê tweets theo username
SELECT username,
       COUNT(*) AS total_tweets,
       AVG(CAST(like_count AS INT)) AS avg_likes,
       MAX(CAST(retweet_count AS INT)) AS max_retweets
FROM s3.root.`tweets/2026/**/*.csv`
GROUP BY username
ORDER BY avg_likes DESC;

-- Top hashtags
SELECT hashtags, COUNT(*) AS frequency
FROM s3.root.`tweets/2026/**/*.csv`
WHERE hashtags <> ''
GROUP BY hashtags
ORDER BY frequency DESC
LIMIT 10;
```

## CI/CD Pipeline

Dự án sử dụng **GitHub Actions** cho CI/CD tự động:

```
Push to main → Lint (flake8 + yamllint) → Deploy to EC2 (SSH)
```

Xem: [.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml)

## Monitoring

Health check script tự động kiểm tra toàn bộ hệ thống:

```bash
# Chạy thủ công
bash scripts/health-check.sh

# Cấu hình cron (mỗi 5 phút)
crontab -e
*/5 * * * * /home/ubuntu/twitter-data-lakehouse/scripts/health-check.sh >> /var/log/lakehouse-health.log 2>&1
```

## Resource Optimization (t3.micro)

Đã tối ưu cho 1GB RAM + 4GB Swap:

| Service | Memory Limit | Kỹ thuật tối ưu |
|---------|-------------|------------------|
| MinIO | 200 MB | GOGC=20 (aggressive Go GC) |
| Drill | 384 MB | SerialGC, CompressedOops, MaxMetaspace=128m |
| Superset | 256 MB | Single gunicorn worker |
| PostgreSQL | 100 MB | shared_buffers=32MB, work_mem=1MB |
| Airflow Scheduler | 256 MB | SequentialExecutor, min_file_process_interval=60s |
| Airflow Webserver | 256 MB | 1 worker, lazy import pyarrow |

> 📖 Chi tiết tối ưu: [docs/architecture.md → Section 5](docs/architecture.md#5-tối-ưu-hóa-cho-môi-trường-low-memory)

## Project Structure

```
├── app/
│   └── dags/
│       ├── twitter_etl.py          # Airflow DAG (main pipeline)
│       └── mock_twitter_data.py    # Mock data generator (8 users)
├── conf/
│   └── drill/
│       ├── core-site.xml           # Drill → MinIO S3A config
│       └── storage-plugins-override.conf
├── docs/
│   └── architecture.md             # 📖 Architecture & Lakehouse docs
├── scripts/
│   ├── init.sh                     # EC2 setup script
│   └── health-check.sh             # Monitoring health check
├── .github/
│   └── workflows/
│       └── ci-cd.yml               # GitHub Actions CI/CD
├── docker-compose.yaml             # All services (cloud-optimized)
├── airflow.Dockerfile              # Custom Airflow image
├── superset_drill.Dockerfile       # Superset + Drill connector
├── sample.env                      # Environment template
├── Makefile                        # Build automation
└── README.md
```

## Troubleshooting

### Services không start?
```bash
# Check logs
docker compose logs <service-name>

# Check memory
free -h
docker stats --no-stream
```

### Out of Memory?
```bash
# Kiểm tra swap
sudo swapon --show

# Tăng swap nếu cần
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Drill không kết nối MinIO?
- Kiểm tra MinIO đã healthy: `docker compose ps minio`
- Credentials trong `conf/drill/core-site.xml` phải khớp với `.env`

## License

MIT License — see [LICENSE](LICENSE) for details.
