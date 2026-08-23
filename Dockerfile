FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Keep an empty, fully migrated database in the image. Railway's mounted
# /data volume is initialized from this seed by docker-entrypoint.sh.
RUN mkdir -p /data/kids-quiz /app/seed \
    && DB_PATH=/app/seed/kids-quiz.sqlite3 python scripts/migrate.py \
    && chmod +x /app/docker-entrypoint.sh

ENV DB_PATH=/data/kids-quiz/kids-quiz.sqlite3

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
