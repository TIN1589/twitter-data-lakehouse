FROM apache/airflow:2.5.0-python3.10

# >>> MEM: Install boto3 for S3/MinIO uploads + pyarrow for Parquet output
# PyArrow is loaded lazily (only during Parquet write) and freed immediately
# after use to minimize memory footprint on t3.micro.
RUN pip install --no-cache-dir \
    boto3==1.34.0 \
    pyarrow==14.0.2
