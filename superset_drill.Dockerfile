FROM apache/superset:2.1.3
# Install Apache Drill SQL connector + dependencies
USER root
RUN pip install --no-cache-dir \
    sqlalchemy-drill==1.1.4 \
    JPype1==1.5.0 \
    pyodbc==4.0.39
USER superset