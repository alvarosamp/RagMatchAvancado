ARG API_IMAGE=ragmatch-api:qa
FROM ${API_IMAGE}
WORKDIR /app
RUN pip install --no-cache-dir 'coverage>=7.10,<8' 'pytest>=8,<10'
COPY backend/app /app/app
COPY backend/scripts /app/scripts
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini
COPY qa /qa
COPY analytics /workspace/analytics
COPY backend/scripts /workspace/backend/scripts
COPY backend/alembic /workspace/backend/alembic
COPY backend/alembic.ini /workspace/backend/alembic.ini
ENV PYTHONPATH=/app
CMD ["python", "/qa/serve.py"]
