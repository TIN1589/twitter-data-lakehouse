FROM apache/airflow:2.5.0-python3.10

# >>> MEM: Chỉ cài boto3 — đã loại bỏ pandas (~80MB) và pyarrow (~50MB)
# ETL pipeline giờ dùng csv module (stdlib) thay vì Pandas DataFrame.
# Tiết kiệm ~130MB RAM mỗi lần chạy DAG.
RUN pip install --no-cache-dir \
    boto3==1.34.0
