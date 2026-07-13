"""Image storage for campaign photos (Phase 3).

Two modes, chosen by whether S3_BUCKET is set — the same "prod vs local" split
`db.py` uses for Postgres-vs-SQLite, so the whole upload flow is testable
locally without any AWS:

  • S3_BUCKET set   -> upload to Amazon S3, return the public https object URL.
  • S3_BUCKET unset -> save under backend/media/, return a URL served by the API
    at /media/... (see the StaticFiles mount in main.py).

Phase 4 (receipt uploads) reuses this module unchanged.
"""
import os
import uuid
from pathlib import Path

from fastapi import UploadFile

# backend/media — an absolute path so it's the same dir no matter the cwd.
MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"

# Where the local files are reachable from a browser (frontend may be on a
# different origin). Only used in local mode; S3 mode builds an S3 URL instead.
LOCAL_BASE_URL = os.environ.get("CIRQLE_MEDIA_BASE", "http://localhost:8000")

_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


class StorageError(RuntimeError):
    """Bad input — e.g. the upload isn't an image (maps to HTTP 400)."""


class StorageUploadError(StorageError):
    """The store itself failed — S3 down, disk error (maps to HTTP 503)."""


def _extension(file: UploadFile) -> str:
    """Pick a file extension from the content type, then the original name."""
    ext = _EXT_BY_TYPE.get((file.content_type or "").lower())
    if ext:
        return ext
    suffix = Path(file.filename or "").suffix.lower()
    return suffix if suffix else ".jpg"


def upload_image(file: UploadFile) -> str:
    """Store one uploaded image and return its public URL.

    Raises StorageError if the file isn't an image or the write/upload fails.
    """
    if not (file.content_type or "").lower().startswith("image/"):
        raise StorageError(f"'{file.filename}' is not an image.")

    data = file.file.read()
    if not data:
        raise StorageError(f"'{file.filename}' is empty.")

    key = f"{uuid.uuid4().hex}{_extension(file)}"
    bucket = os.environ.get("S3_BUCKET")

    if bucket:
        region = os.environ.get("AWS_REGION", "eu-west-2")
        try:
            import boto3  # imported lazily so local dev needs no boto3/AWS

            # No per-object ACL: modern buckets disable ACLs ("bucket owner
            # enforced"); public read is granted by the bucket policy instead.
            boto3.client("s3", region_name=region).put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=file.content_type,
            )
        except Exception as exc:  # noqa: BLE001 — surface any AWS failure as one type
            raise StorageUploadError(f"S3 upload failed: {exc}") from exc
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    # Local mode: write to backend/media/ and serve via /media.
    try:
        MEDIA_DIR.mkdir(exist_ok=True)
        (MEDIA_DIR / key).write_bytes(data)
    except OSError as exc:
        raise StorageUploadError(f"Could not write image to disk: {exc}") from exc
    return f"{LOCAL_BASE_URL}/media/{key}"
