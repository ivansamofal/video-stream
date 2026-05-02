import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.limiter import limiter, user_or_ip
from app.models.user import User
from app.models.video import Video, VideoStatus
from app.schemas.video import (
    UploadInitiateRequest,
    UploadInitiateResponse,
    VideoListResponse,
    VideoResponse,
    VideoUploadResponse,
)
from app.services.storage import (
    delete_object_async,
    delete_prefix_async,
    generate_upload_presigned_url_async,
    public_url,
    upload_fileobj_async,
)

router = APIRouter(prefix="/videos", tags=["videos"])

ALLOWED_MIME_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/webm", "video/mpeg",
}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


def _build_response(video: Video) -> VideoResponse:
    data = VideoResponse.model_validate(video)
    if video.hls_base_path and video.status == VideoStatus.published:
        data.master_playlist_url = public_url(f"{video.hls_base_path}/master.m3u8")
    if video.thumbnail_path:
        data.thumbnail_url = public_url(video.thumbnail_path)
    return data


@router.post("/initiate-upload", response_model=UploadInitiateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour", key_func=user_or_ip)
async def initiate_upload(
    request: Request,
    body: UploadInitiateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported media type: {body.content_type}")

    video = Video(
        title=body.title,
        description=body.description or None,
        owner_id=current_user.id,
        status=VideoStatus.uploading,
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)

    suffix = Path(body.filename).suffix or ".bin"
    object_key = f"raw/{video.id}/original{suffix}"
    video.raw_object_key = object_key
    await db.commit()

    upload_url = await generate_upload_presigned_url_async(object_key, body.content_type)
    return UploadInitiateResponse(video_id=video.id, upload_url=upload_url)


@router.post("/{video_id}/confirm", response_model=VideoUploadResponse)
async def confirm_upload(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    if video.status != VideoStatus.uploading:
        raise HTTPException(status_code=409, detail="Upload already confirmed or in wrong state")

    video.status = VideoStatus.processing
    await db.commit()

    from app.tasks.transcode import transcode_video
    transcode_video.delay(video.id, video.raw_object_key)

    return video


@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour", key_func=user_or_ip)
async def upload_video(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported media type: {file.content_type}")

    video = Video(
        title=title,
        description=description or None,
        owner_id=current_user.id,
        status=VideoStatus.uploading,
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)

    object_key = f"raw/{video.id}/{file.filename}"
    await upload_fileobj_async(file.file, object_key, content_type=file.content_type)

    video.raw_object_key = object_key
    video.status = VideoStatus.processing
    await db.commit()

    # Queue transcoding task
    from app.tasks.transcode import transcode_video
    transcode_video.delay(video.id, object_key)

    return video


@router.get("/", response_model=VideoListResponse)
async def list_videos(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    total = await db.scalar(
        select(func.count()).where(Video.status == VideoStatus.published)
    )
    result = await db.execute(
        select(Video)
        .where(Video.status == VideoStatus.published)
        .order_by(Video.published_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    videos = result.scalars().all()
    return VideoListResponse(
        items=[_build_response(v) for v in videos],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: int, db: AsyncSession = Depends(get_db)):
    video = await db.get(Video, video_id)
    if not video or video.status != VideoStatus.published:
        raise HTTPException(status_code=404, detail="Video not found")
    return _build_response(video)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not allowed")

    if video.raw_object_key:
        await delete_object_async(video.raw_object_key)
    if video.hls_base_path:
        await delete_prefix_async(f"{video.hls_base_path}/")
    if video.thumbnail_path:
        await delete_object_async(video.thumbnail_path)

    await db.delete(video)
    await db.commit()
