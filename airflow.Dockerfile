FROM apache/airflow:2.5.0-python3.10

# Pre-install dependencies to avoid runtime pip install (OOM risk on t3.micro)
RUN pip install --no-cache-dir \
    boto3==1.34.0 \
    pandas==1.5.3 \
    pyarrow==14.0.2 \
    pydantic==2.5.0 \
    pytest==7.4.3
