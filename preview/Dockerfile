ARG API_IMAGE=alvarocareli/ragmatch-api:sha-a6a1c110c852dfb14c93c8359290961385d8cc56
FROM ${API_IMAGE}
WORKDIR /app
RUN pip install --no-cache-dir 'coverage>=7.10,<8' 'pytest>=8,<10'
COPY backend/app /app/app
COPY backend/scripts /app/scripts
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini
COPY qa /qa
COPY preview /preview
COPY tests /preview/tests
ENV PYTHONPATH=/app
CMD ["python", "/preview/serve.py"]
