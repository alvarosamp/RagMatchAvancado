FROM python:3.12-slim
WORKDIR /workspace
COPY analytics/requirements.txt /tmp/analytics-requirements.txt
RUN pip install --no-cache-dir -r /tmp/analytics-requirements.txt
COPY analytics/requirements-dbt.txt /tmp/dbt-requirements.txt
RUN python -m venv /opt/dbt && /opt/dbt/bin/pip install --no-cache-dir -r /tmp/dbt-requirements.txt
COPY backend/app /workspace/backend/app
COPY analytics /workspace/analytics
ENV PYTHONPATH=/workspace/backend:/workspace PYTHONUNBUFFERED=1 BACKEND_LOG_DIR=/tmp/backend-logs MARKET_DBT_BIN=/opt/dbt/bin/dbt
ENV DBT_LOG_PATH=/tmp/dbt-logs DBT_TARGET_PATH=/tmp/dbt-target
ENV HOME=/tmp PREFECT_HOME=/tmp/.prefect
USER 10001:10001
CMD ["python", "-m", "app.market_intelligence.worker"]
