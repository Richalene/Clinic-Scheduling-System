"""Private avatars, normalized to JPEG without original metadata."""
import base64
from io import BytesIO
from pathlib import Path
import os
import tempfile
import warnings

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from app.config import settings


def picture_path(user_id: int) -> Path:
    return Path(settings.PROFILE_PICTURE_DIR) / f"{int(user_id)}.jpg"


def read_picture(user_id: int) -> str | None:
    try:
        content = picture_path(user_id).read_bytes()
    except FileNotFoundError:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(content).decode("ascii")


def store_picture(user_id: int, content: bytes):
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Choose a picture smaller than 2 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Unsupported image format")
                if source.width * source.height > 16_000_000:
                    raise ValueError("Image exceeds 16 megapixels")
                source.load()
                normalized = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), (256, 256))
                output = BytesIO()
                normalized.save(output, format="JPEG", quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(400, "Choose a valid JPEG, PNG, or WebP image up to 16 megapixels") from exc
    target = picture_path(user_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(output.getvalue())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def remove_picture(user_id: int):
    picture_path(user_id).unlink(missing_ok=True)
