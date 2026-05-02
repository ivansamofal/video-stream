# VideoStream

A self-hosted video streaming platform. Upload videos, transcode them to adaptive HLS, and stream with a multi-quality player.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TypeScript + Tailwind CSS + hls.js |
| API | FastAPI (async) + SQLAlchemy + asyncpg |
| Auth | JWT access tokens (15 min) + httponly refresh cookies (7 days) |
| Transcoding | Celery worker + ffmpeg → HLS (360p / 720p / 1080p) |
| Object storage | MinIO (S3-compatible) |
| Database | PostgreSQL 16 |
| Queue / cache | Redis 7 |
| Reverse proxy | nginx |

---

## Running locally

### Prerequisites

- Docker and Docker Compose

### 1. Create `.env`

```env
# Postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=videostream

# SQLAlchemy
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/videostream

# Redis
REDIS_URL=redis://redis:6379/0

# JWT — generate with: openssl rand -hex 32
SECRET_KEY=change-me

# MinIO
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=videostream
MINIO_USE_SSL=false

# Public URL the browser uses to fetch HLS segments directly from MinIO
PUBLIC_MINIO_URL=http://localhost:9000
```

### 2. Start all services

```bash
docker compose up -d --build
```

The following services start:

| Service | URL |
|---|---|
| App (nginx) | http://localhost |
| MinIO console | http://localhost:9001 |
| API docs | http://localhost/api/docs |

Migrations run automatically on startup.

### 3. Create an admin user (optional)

```bash
docker compose exec api python scripts/create_admin.py admin@example.com yourpassword
```

Admin users can see all videos by status at `/admin` and manually approve or reject uploads.

### 4. Stop

```bash
docker compose down
```

Add `-v` to also delete the database and MinIO volumes.

---

## How it works

### Request flow

```
Browser → nginx :80
              ├─ /api/*  → FastAPI :8000
              └─ /*      → Vue SPA :80 (frontend container)

Browser → MinIO :9000  (HLS segments — direct, no proxy)
```

nginx proxies API and frontend traffic. HLS video segments are fetched by the browser **directly from MinIO on port 9000**, bypassing nginx entirely. MinIO has a public bucket policy so no credentials are needed for playback.

### Authentication

1. `POST /api/auth/register` — creates account
2. `POST /api/auth/login` — returns a short-lived JWT (15 min) in the response body and sets an httponly `refresh_token` cookie (7 days)
3. The frontend stores the JWT in memory (not localStorage) and attaches it as `Authorization: Bearer <token>` on every API request
4. When the JWT expires, the axios interceptor automatically calls `POST /api/auth/refresh` using the cookie to get a new JWT — transparent to the user
5. `POST /api/auth/logout` — deletes the refresh cookie

### Video upload and transcoding

```
Browser
  │
  ├─ POST /api/videos/upload (multipart, title + file)
  │     │
  │     ├─ Save raw file to MinIO at raw/{id}/{filename}
  │     ├─ Create Video row (status: processing)
  │     └─ Push transcode_video task to Redis queue
  │
Celery worker picks up the task:
  ├─ Download raw file from MinIO to a temp directory
  ├─ ffprobe → get duration
  ├─ ffmpeg × 3 passes → 360p, 720p, 1080p HLS segments + playlists
  ├─ Upload all .m3u8 and .ts files to MinIO at hls/{id}/
  └─ Update Video row (status: published, hls_base_path, duration_seconds)
```

After the worker finishes (~30–60 seconds for a short video), the video appears on the home page.

### HLS playback

The API returns a `master_playlist_url` pointing to MinIO, e.g.:

```
http://localhost:9000/videostream/hls/3/master.m3u8
```

The master playlist lists three quality variants. hls.js in the browser selects the best quality based on available bandwidth and fetches `.ts` segments directly from MinIO.

### Video statuses

| Status | Meaning |
|---|---|
| `uploading` | Upload request received, not yet saved to storage |
| `processing` | Raw file saved, transcoding task queued or running |
| `published` | Transcoding complete, visible on home page |
| `failed` | ffmpeg error — check `error_message` in admin panel |
| `pending_review` | Transcoding complete, waiting for admin approval (not used in default config) |
| `rejected` | Rejected by admin (not used in default config) |

### Admin panel

Available at `/admin` for users with `is_admin = true`. Lists all videos with status filters and lets you manually approve or reject videos in `pending_review` status.

---

## Project structure

```
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py          # Auth dependencies (get_current_user, get_admin_user)
│   │   │   └── routes/
│   │   │       ├── auth.py      # register, login, refresh, logout, me
│   │   │       ├── videos.py    # upload, list, get
│   │   │       └── admin.py     # list all, approve, reject
│   │   ├── core/
│   │   │   ├── config.py        # Settings from environment variables
│   │   │   ├── database.py      # Async SQLAlchemy engine and session
│   │   │   └── security.py      # Password hashing, JWT encode/decode
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   └── video.py         # VideoStatus enum + Video model
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── storage.py       # MinIO/S3 upload, download, public URL
│   │   │   └── transcoding.py   # ffmpeg HLS transcoding, master playlist
│   │   ├── tasks/
│   │   │   └── transcode.py     # Celery task: download → transcode → upload → publish
│   │   └── main.py              # FastAPI app, CORS, lifespan (bucket + migrations)
│   ├── alembic/                 # Database migrations
│   ├── scripts/
│   │   └── create_admin.py      # CLI script to create or promote an admin user
│   ├── entrypoint.sh            # Wait for DB → run migrations → start uvicorn
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/client.ts        # Axios instance with JWT injection and auto-refresh
│       ├── stores/auth.ts       # Pinia auth store (login, register, logout, restore session)
│       ├── router/index.ts      # Vue Router with auth guards
│       └── views/
│           ├── HomeView.vue     # Paginated video grid
│           ├── WatchView.vue    # hls.js player
│           ├── UploadView.vue   # Drag-and-drop upload with progress bar
│           ├── LoginView.vue
│           ├── RegisterView.vue
│           └── AdminView.vue    # Video moderation panel
├── nginx/
│   └── nginx.conf               # Proxy: /api/ → FastAPI, / → Vue SPA
└── docker-compose.yml
```
