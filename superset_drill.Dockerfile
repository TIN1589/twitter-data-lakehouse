FROM apache/superset:2.1.3
# Install Apache Drill SQL connector
USER root
RUN pip install --no-cache-dir sqlalchemy-drill==1.1.4
USER superset