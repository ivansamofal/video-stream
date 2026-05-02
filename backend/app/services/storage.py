import asyncio
import functools
import logging
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _public_s3_client():
    """S3 client using the browser-accessible URL — presigned URLs must use this host."""
    return boto3.client(
        "s3",
        endpoint_url=settings.public_minio_url,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket_exists() -> None:
    client = _s3_client()
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.minio_bucket)
        # Make bucket publicly readable so HLS segments stream without auth
        client.put_bucket_policy(
            Bucket=settings.minio_bucket,
            Policy=f"""{{
                "Version":"2012-10-17",
                "Statement":[{{
                    "Effect":"Allow",
                    "Principal":"*",
                    "Action":"s3:GetObject",
                    "Resource":"arn:aws:s3:::{settings.minio_bucket}/*"
                }}]
            }}""",
        )
        logger.info("Created bucket: %s", settings.minio_bucket)
    # Allow browsers to PUT directly via presigned URLs (set unconditionally so it
    # survives container restarts against an existing bucket).
    try:
        client.put_bucket_cors(
            Bucket=settings.minio_bucket,
            CORSConfiguration={
                "CORSRules": [{
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "PUT"],
                    "AllowedOrigins": ["*"],
                    "ExposeHeaders": ["ETag"],
                }]
            },
        )
    except ClientError as exc:
        logger.warning("Could not set bucket CORS: %s", exc)


def upload_file(local_path: str, object_key: str, content_type: str = "application/octet-stream") -> None:
    client = _s3_client()
    client.upload_file(
        local_path,
        settings.minio_bucket,
        object_key,
        ExtraArgs={"ContentType": content_type},
    )


def upload_fileobj(file_obj, object_key: str, content_type: str = "application/octet-stream") -> None:
    client = _s3_client()
    client.upload_fileobj(
        file_obj,
        settings.minio_bucket,
        object_key,
        ExtraArgs={"ContentType": content_type},
    )


def download_file(object_key: str, local_path: str) -> None:
    client = _s3_client()
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    client.download_file(settings.minio_bucket, object_key, local_path)


def upload_directory(local_dir: str, prefix: str) -> None:
    """Upload all files in a local directory to MinIO under the given prefix."""
    client = _s3_client()
    for path in Path(local_dir).rglob("*"):
        if path.is_file():
            relative = path.relative_to(local_dir)
            object_key = f"{prefix}/{relative}"
            content_type = "application/x-mpegURL" if path.suffix == ".m3u8" else "video/MP2T"
            client.upload_file(
                str(path),
                settings.minio_bucket,
                object_key,
                ExtraArgs={"ContentType": content_type},
            )


def public_url(object_key: str) -> str:
    return f"{settings.public_minio_url}/{settings.minio_bucket}/{object_key}"


async def upload_fileobj_async(file_obj, object_key: str, content_type: str = "application/octet-stream") -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        functools.partial(upload_fileobj, file_obj, object_key, content_type=content_type),
    )


async def ensure_bucket_exists_async() -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, ensure_bucket_exists)


def delete_object(object_key: str) -> None:
    _s3_client().delete_object(Bucket=settings.minio_bucket, Key=object_key)


def delete_prefix(prefix: str) -> None:
    """Delete all objects whose key starts with prefix (e.g. 'hls/3/').  """
    client = _s3_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.minio_bucket, Prefix=prefix):
        objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=settings.minio_bucket, Delete={"Objects": objects})


async def delete_object_async(object_key: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, delete_object, object_key)


async def delete_prefix_async(prefix: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, delete_prefix, prefix)


def generate_upload_presigned_url(object_key: str, content_type: str, expires: int = 3600) -> str:
    """Return a presigned PUT URL the browser can use to upload directly to MinIO."""
    client = _public_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.minio_bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires,
    )


async def generate_upload_presigned_url_async(object_key: str, content_type: str, expires: int = 3600) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(generate_upload_presigned_url, object_key, content_type, expires),
    )
