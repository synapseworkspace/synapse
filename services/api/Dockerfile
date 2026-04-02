FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/api /app/services/api
COPY services/shared /app/services/shared

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -e /app/services/api

ENV PYTHONPATH=/app/services:/app/services/api

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
