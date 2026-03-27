FROM python:3.12-slim

WORKDIR /app

# Copy everything needed for install
COPY pyproject.toml .
COPY src/ src/

# Install the package (includes dependencies)
RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/src
ENV SQLITE_DB_PATH=/tmp/scheduler.db

RUN useradd -m -s /bin/bash scheduler && chown -R scheduler:scheduler /app /tmp
USER scheduler

EXPOSE 8080

CMD ["uvicorn", "scheduler.controlplane.server:app", "--host", "0.0.0.0", "--port", "8080"]
