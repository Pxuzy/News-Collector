FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    NEWS_COLLECTOR_ROOT=/app \
    PYTHONPATH=/app/scripts:/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .
RUN mkdir -p data output logs cron/output

EXPOSE 8899

CMD ["python", "-m", "compileall", "-q", "multi_source_news.py", "scripts", "sources"]
