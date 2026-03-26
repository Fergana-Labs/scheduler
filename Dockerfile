FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ src/

EXPOSE 8080

CMD ["uvicorn", "scheduler.controlplane.server:app", "--host", "0.0.0.0", "--port", "8080"]
