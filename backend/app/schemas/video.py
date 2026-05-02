from datetime import datetime

from pydantic import BaseModel

from app.models.video import VideoStatus


class VideoUploadResponse(BaseModel):
    id: int
    title: str
    status: VideoStatus

    model_config = {"from_attributes": True}


class UploadInitiateRequest(BaseModel):
    title: str
    description: str = ""
    filename: str
    content_type: str


class UploadInitiateResponse(BaseModel):
    video_id: int
    upload_url: str


class VideoResponse(BaseModel):
    id: int
    title: str
    description: str | None
    status: VideoStatus
    duration_seconds: int | None
    owner_id: int
    created_at: datetime
    published_at: datetime | None
    master_playlist_url: str | None = None
    thumbnail_url: str | None = None

    model_config = {"from_attributes": True}


class VideoAdminResponse(VideoResponse):
    raw_object_key: str | None
    hls_base_path: str | None
    error_message: str | None


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    total: int
    page: int
    page_size: int
