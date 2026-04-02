FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/mcp /app/services/mcp
COPY services/shared /app/services/shared

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -e /app/services/mcp

ENV PYTHONPATH=/app/services:/app/services/mcp

EXPOSE 8091

CMD ["python", "services/mcp/scripts/run_mcp_server.py", "--transport", "http"]
