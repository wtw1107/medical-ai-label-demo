from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError


def get_image_size_from_bytes(image_bytes: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(image_bytes)) as image:
        return image.width, image.height


def get_image_size_from_path(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.width, image.height


def validate_image_bytes(image_bytes: bytes) -> tuple[int, int]:
    try:
        return get_image_size_from_bytes(image_bytes)
    except UnidentifiedImageError as exc:
        raise ValueError("Unsupported or corrupted image file.") from exc
