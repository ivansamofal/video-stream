#!/bin/sh
set -e

echo "Waiting for database..."
until python -c "
import asyncio, asyncpg, os, sys
url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/videostream')
url = url.replace('postgresql+asyncpg://', 'postgresql://')
async def check():
    try:
        conn = await asyncpg.connect(url)
        await conn.close()
    except Exception as e:
        sys.exit(1)
asyncio.run(check())
"; do
  echo "DB not ready, retrying..."
  sleep 2
done

echo "Running migrations..."
alembic upgrade head

echo "Starting API..."
WORKERS=${UVICORN_WORKERS:-4}
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "$WORKERS"
