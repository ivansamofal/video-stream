import logging
import shutil
import tempfile

from celery import Celery

from app.core.config import settings
from app.services import storage, transcoding

logger = logging.getLogger(__name__)

celery_app = Celery("videostream", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_track_started = True


@celery_app.task(bind=True, name="transcode_video", max_retries=2)
def transcode_video(self, video_id: int, raw_object_key: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.user import User  # noqa: F401 — required for SQLAlchemy mapper
    from app.models.video import Video, VideoStatus

    # Use sync engine inside Celery worker
    sync_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        video = db.get(Video, video_id)
        if not video:
            logger.error("Video %s not found", video_id)
            return

        video.status = VideoStatus.processing
        db.commit()

        with tempfile.TemporaryDirectory() as tmp:
            raw_path = f"{tmp}/raw_input"
            hls_dir = f"{tmp}/hls"

            try:
                logger.info("Downloading raw video %s", raw_object_key)
                storage.download_file(raw_object_key, raw_path)

                duration = transcoding.get_duration(raw_path)
                transcoding.transcode_to_hls(raw_path, hls_dir)

                hls_base = f"hls/{video_id}"
                logger.info("Uploading HLS segments for video %s", video_id)
                storage.upload_directory(hls_dir, hls_base)

                thumbnail_key = None
                try:
                    thumbnail_path = f"{tmp}/thumbnail.jpg"
                    transcoding.generate_thumbnail(raw_path, thumbnail_path, duration)
                    thumbnail_key = f"thumbnails/{video_id}.jpg"
                    storage.upload_file(thumbnail_path, thumbnail_key, content_type="image/jpeg")
                    logger.info("Thumbnail generated for video %s", video_id)
                except Exception:
                    logger.warning("Thumbnail generation failed for video %s, continuing without it", video_id)

                from datetime import datetime, UTC
                video.hls_base_path = hls_base
                video.duration_seconds = duration
                video.thumbnail_path = thumbnail_key
                video.status = VideoStatus.published
                video.published_at = datetime.now(UTC)
                db.commit()
                logger.info("Video %s published", video_id)

            except Exception as exc:
                logger.exception("Transcoding failed for video %s", video_id)
                video.status = VideoStatus.failed
                video.error_message = str(exc)[:1000]
                db.commit()
                raise self.retry(exc=exc, countdown=60)
