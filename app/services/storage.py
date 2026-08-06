"""
Storage abstraction layer for Railway Buckets (S3) with local filesystem fallback.

Railway Buckets provide S3-compatible storage with credentials:
- S3_BUCKET_NAME: The bucket name
- AWS_ACCESS_KEY_ID: S3 access key
- AWS_SECRET_ACCESS_KEY: S3 secret key
- AWS_ENDPOINT_URL: S3 API endpoint (e.g., https://storage.railway.app)
- AWS_DEFAULT_REGION: Region (typically "auto")

In development (no credentials), files are stored locally in ./uploads/documents
"""

import os
import logging
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# --- S3 Configuration ---
USE_S3 = all([
    os.environ.get("S3_BUCKET_NAME"),
    os.environ.get("AWS_ACCESS_KEY_ID"),
    os.environ.get("AWS_SECRET_ACCESS_KEY"),
    os.environ.get("AWS_ENDPOINT_URL"),
])

# Local fallback directory
LOCAL_UPLOAD_DIR = os.environ.get("UPLOADS_VOLUME_PATH", "uploads/documents")


def get_s3_client():
    """Create and return a boto3 S3 client configured for Railway Buckets."""
    if not USE_S3:
        raise RuntimeError("S3 credentials not configured. Use local storage.")

    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_DEFAULT_REGION", "auto"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )


def get_s3_key(state: str, filename: str, municipality: Optional[str] = None) -> str:
    """Generate S3 object key from state/filename/municipality."""
    if municipality:
        return f"documents/{state}/{municipality}/{filename}"
    return f"documents/{state}/{filename}"


def get_local_path(state: str, filename: str, municipality: Optional[str] = None) -> str:
    """Generate local file path."""
    if municipality:
        return os.path.join(LOCAL_UPLOAD_DIR, state, municipality, filename)
    return os.path.join(LOCAL_UPLOAD_DIR, state, filename)


# --- Core Storage Operations ---

def upload_file(file_content: bytes, state: str, filename: str,
                municipality: Optional[str] = None) -> str:
    """
    Upload a file to storage (S3 or local).

    Returns:
        str: S3 key or local file path (for database storage)
    """
    if USE_S3:
        return _upload_to_s3(file_content, state, filename, municipality)
    else:
        return _upload_local(file_content, state, filename, municipality)


def download_file(storage_path: str) -> bytes:
    """
    Download file content from storage.

    Args:
        storage_path: S3 key or local file path

    Returns:
        bytes: File content
    """
    if USE_S3:
        return _download_from_s3(storage_path)
    else:
        return _download_local(storage_path)


def delete_file(storage_path: str) -> bool:
    """
    Delete a file from storage.

    Args:
        storage_path: S3 key or local file path

    Returns:
        bool: True if successful
    """
    if USE_S3:
        return _delete_from_s3(storage_path)
    else:
        return _delete_local(storage_path)


def get_temp_file_for_processing(storage_path: str) -> str:
    """
    Get a temporary local file path for processing (e.g., PyPDFLoader).

    For S3: Downloads to temp file, returns path (caller must clean up)
    For Local: Returns the path directly (no cleanup needed)

    Returns:
        str: Local file path
    """
    if USE_S3:
        content = _download_from_s3(storage_path)
        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    else:
        return storage_path


def cleanup_temp_file(temp_path: str):
    """Clean up temporary file if needed."""
    if os.path.exists(temp_path):
        try:
            os.unlink(temp_path)
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {temp_path}: {e}")


# --- S3 Operations ---

def _upload_to_s3(file_content: bytes, state: str, filename: str,
                  municipality: Optional[str] = None) -> str:
    """Upload file to Railway Bucket."""
    s3 = get_s3_client()
    key = get_s3_key(state, filename, municipality)
    bucket = os.environ["S3_BUCKET_NAME"]

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=file_content,
        ContentType="application/pdf",
    )

    logger.info(f"Uploaded to S3: s3://{bucket}/{key}")
    return key


def _download_from_s3(key: str) -> bytes:
    """Download file from Railway Bucket."""
    s3 = get_s3_client()
    bucket = os.environ["S3_BUCKET_NAME"]

    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def _delete_from_s3(key: str) -> bool:
    """Delete file from Railway Bucket."""
    try:
        s3 = get_s3_client()
        bucket = os.environ["S3_BUCKET_NAME"]
        s3.delete_object(Bucket=bucket, Key=key)
        logger.info(f"Deleted from S3: s3://{bucket}/{key}")
        return True
    except Exception as e:
        logger.error(f"Error deleting from S3: {e}")
        return False


# --- Local Operations ---

def _upload_local(file_content: bytes, state: str, filename: str,
                  municipality: Optional[str] = None) -> str:
    """Upload file to local filesystem."""
    file_path = get_local_path(state, filename, municipality)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(file_content)

    logger.info(f"Saved locally: {file_path}")
    return file_path


def _download_local(file_path: str) -> bytes:
    """Read file from local filesystem."""
    with open(file_path, "rb") as f:
        return f.read()


def _delete_local(file_path: str) -> bool:
    """Delete file from local filesystem."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted locally: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error deleting local file: {e}")
        return False
