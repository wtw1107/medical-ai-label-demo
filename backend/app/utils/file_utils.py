from __future__ import annotations

import os
from pathlib import Path
from zipfile import ZipInfo

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/bmp",
    "image/tiff",
    "image/webp",
}


def normalize_filename(filename: str) -> str:
    name = Path(filename).name.replace("\x00", "")
    return name or "file"


def get_file_suffix(filename: str) -> str:
    return Path(filename).suffix.lower()


def is_allowed_image_file(filename: str) -> bool:
    return get_file_suffix(filename) in ALLOWED_IMAGE_EXTENSIONS


def is_zip_file(filename: str, content_type: str | None = None) -> bool:
    suffix = get_file_suffix(filename)
    if suffix == ".zip":
        return True
    if content_type:
        return content_type == "application/zip"
    return False


def build_unique_filename(original_filename: str, suffix: str) -> str:
    stem = Path(original_filename).stem or "image"
    safe_stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem).strip("_")
    safe_stem = safe_stem or "image"
    return f"{safe_stem}{suffix}"


def safe_join(base_dir: Path, *parts: str) -> Path:
    candidate = base_dir.joinpath(*parts)
    resolved_base = base_dir.resolve()
    resolved_candidate = candidate.resolve(strict=False)
    if resolved_candidate != resolved_base and resolved_base not in resolved_candidate.parents:
        raise ValueError("Unsafe path traversal detected.")
    return candidate


def is_dir_entry(zip_info: ZipInfo) -> bool:
    return zip_info.is_dir()
