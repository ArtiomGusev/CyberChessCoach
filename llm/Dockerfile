FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["sh", "-c", "uvicorn host_app:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-4}"]
