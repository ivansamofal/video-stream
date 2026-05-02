from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.core.database import get_db
from app.models.user import User
from app.models.video import Video, VideoStatus
from app.schemas.video import VideoAdminResponse, VideoListResponse
from app.services.storage import public_url

router = APIRouter(prefix="/admin", tags=["admin"])


def _build_admin_response(video: Video) -> VideoAdminResponse:
    data = VideoAdminResponse.model_validate(video)
    if video.hls_base_path:
        data.master_playlist_url = public_url(f"{video.hls_base_path}/master.m3u8")
    return data


@router.get("/videos", response_model=VideoListResponse)
async def list_all_videos(
    page: int = 1,
    page_size: int = 20,
    status: VideoStatus | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    query = select(Video)
    count_query = select(func.count()).select_from(Video)
    if status:
        query = query.where(Video.status == status)
        count_query = count_query.where(Video.status == status)

    offset = (page - 1) * page_size
    total = await db.scalar(count_query)
    result = await db.execute(
        query.order_by(Video.created_at.desc()).offset(offset).limit(page_size)
    )
    videos = result.scalars().all()
    return VideoListResponse(
        items=[_build_admin_response(v) for v in videos],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.patch("/videos/{video_id}/approve", response_model=VideoAdminResponse)
async def approve_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status != VideoStatus.pending_review:
        raise HTTPException(status_code=400, detail=f"Cannot approve video in status '{video.status}'")

    video.status = VideoStatus.published
    video.published_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(video)
    return _build_admin_response(video)


@router.patch("/videos/{video_id}/reject", response_model=VideoAdminResponse)
async def reject_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status != VideoStatus.pending_review:
        raise HTTPException(status_code=400, detail=f"Cannot reject video in status '{video.status}'")

    video.status = VideoStatus.rejected
    await db.commit()
    await db.refresh(video)
    return _build_admin_response(video)
