# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY .env.example .

RUN useradd --create-home --shell /bin/bash atlas \
    && mkdir -p /app/logs \
    && chown -R atlas:atlas /app
USER atlas

ENTRYPOINT ["python", "-m", "atlas_trader.main"]
CMD ["--mode", "paper"]
