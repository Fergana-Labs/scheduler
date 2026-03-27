FROM python:3.12-slim

WORKDIR /app

# Create data directory for SQLite volume mount
RUN mkdir -p /data

# Copy everything needed for install
COPY pyproject.toml .
COPY src/ src/

# Install the package (includes dependencies)
RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/src
ENV SQLITE_DB_PATH=/data/scheduler.db

EXPOSE 8080

CMD ["uvicorn", "scheduler.controlplane.server:app", "--host", "0.0.0.0", "--port", "8080"]
