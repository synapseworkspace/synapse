FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY packages/synapse-sdk-py /app/packages/synapse-sdk-py
COPY services/shared /app/services/shared
COPY services/worker /app/services/worker

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir \
      "psycopg[binary]>=3.2.0" \
      "openpyxl>=3.1.0" \
      "pypdf>=4.0.0" \
      "requests>=2.31.0" \
    && python -m pip install --no-cache-dir -e /app/packages/synapse-sdk-py

ENV PYTHONPATH=/app/services:/app/services/worker:/app/packages/synapse-sdk-py/src

CMD ["python", "services/worker/scripts/run_worker_loop.py"]
