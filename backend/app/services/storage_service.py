from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import DataType, DatasetStatus, ImageStatus
from app.db.models import Dataset, ImageItem
from app.schemas.dataset import DatasetUploadResponse, ImageItemRead, UploadWarning
from app.utils.file_utils import (
    build_unique_filename,
    is_allowed_image_file,
    is_dir_entry,
    is_zip_file,
    normalize_filename,
    safe_join,
)
from app.utils.image_utils import validate_image_bytes

logger = logging.getLogger(__name__)


@dataclass
class StoredImage:
    filename: str
    file_path: str
    file_url: str
    width: int
    height: int


def _save_bytes_to_path(content: bytes, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def _store_image_bytes(
    *,
    image_bytes: bytes,
    original_filename: str,
    images_dir: Path,
    dataset_id: str,
    media_base_url: str,
    unique_token: str,
) -> StoredImage:
    width, height = validate_image_bytes(image_bytes)
    suffix = Path(original_filename).suffix.lower() or ".png"
    saved_filename = f"{unique_token}_{build_unique_filename(original_filename, suffix)}"
    file_path = safe_join(images_dir, saved_filename)
    _save_bytes_to_path(image_bytes, file_path)
    relative_url = f"/datasets/{dataset_id}/images/{saved_filename}"
    file_url = (
        f"{media_base_url.rstrip('/')}{relative_url}"
        if media_base_url
        else f"/media{relative_url}"
    )
    return StoredImage(
        filename=normalize_filename(original_filename),
        file_path=str(file_path),
        file_url=file_url,
        width=width,
        height=height,
    )


def _process_zip_file(
    *,
    upload_file: UploadFile,
    images_dir: Path,
    dataset_id: str,
    media_base_url: str,
    warnings: list[UploadWarning],
) -> list[StoredImage]:
    stored_images: list[StoredImage] = []
    try:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            upload_path = temp_path / normalize_filename(upload_file.filename or "upload.zip")
            upload_path.write_bytes(upload_file.file.read())
            with ZipFile(upload_path) as archive:
                for index, member in enumerate(archive.infolist()):
                    if is_dir_entry(member):
                        continue
                    member_name = normalize_filename(member.filename)
                    if not is_allowed_image_file(member_name):
                        warnings.append(
                            UploadWarning(
                                filename=member_name,
                                message="Skipped non-image file inside zip.",
                            )
                        )
                        continue
                    with archive.open(member) as member_file:
                        image_bytes = member_file.read()
                    try:
                        stored_images.append(
                            _store_image_bytes(
                                image_bytes=image_bytes,
                                original_filename=member_name,
                                images_dir=images_dir,
                                dataset_id=dataset_id,
                                media_base_url=media_base_url,
                                unique_token=f"{index:04d}",
                            )
                        )
                    except ValueError as exc:
                        warnings.append(
                            UploadWarning(
                                filename=member_name,
                                message=str(exc),
                            )
                        )
    except BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Uploaded zip file is invalid or corrupted.") from exc
    return stored_images


def upload_dataset(
    *,
    db: Session,
    name: str,
    created_by: str,
    settings: Settings,
    files: list[UploadFile],
    description: str | None = None,
) -> DatasetUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    dataset = Dataset(
        id=uuid4().hex,
        name=name,
        description=description,
        data_type=DataType.IMAGE.value,
        image_count=0,
        root_dir="",
        status=DatasetStatus.UPLOADED.value,
        created_by=created_by,
    )

    warnings: list[UploadWarning] = []
    stored_images: list[StoredImage] = []

    dataset_id = dataset.id
    dataset_root = settings.ensure_data_root() / "datasets" / dataset_id
    images_dir = dataset_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    try:
        for upload_file in files:
            filename = normalize_filename(upload_file.filename or "upload")
            if is_zip_file(filename, upload_file.content_type):
                stored_images.extend(
                    _process_zip_file(
                        upload_file=upload_file,
                        images_dir=images_dir,
                        dataset_id=dataset_id,
                        media_base_url=settings.media_base_url,
                        warnings=warnings,
                    )
                )
                continue

            if not is_allowed_image_file(filename):
                warnings.append(
                    UploadWarning(
                        filename=filename,
                        message="Skipped non-image file.",
                    )
                )
                continue

            image_bytes = upload_file.file.read()
            try:
                stored_images.append(
                    _store_image_bytes(
                        image_bytes=image_bytes,
                        original_filename=filename,
                        images_dir=images_dir,
                        dataset_id=dataset_id,
                        media_base_url=settings.media_base_url,
                        unique_token=uuid4().hex[:8],
                    )
                )
            except ValueError as exc:
                warnings.append(
                    UploadWarning(
                        filename=filename,
                        message=str(exc),
                    )
                )

    except Exception:
        for path in sorted(images_dir.glob("*")):
            if path.is_file():
                path.unlink(missing_ok=True)
        raise

    if not stored_images:
        raise HTTPException(status_code=400, detail="No valid image files were found in the upload.")

    try:
        dataset.root_dir = str(dataset_root.resolve())
        dataset.image_count = len(stored_images)
        dataset.status = DatasetStatus.READY.value

        db.add(dataset)
        db.flush()

        image_items: list[ImageItem] = []
        for stored_image in stored_images:
            image_item = ImageItem(
                dataset_id=dataset.id,
                filename=stored_image.filename,
                file_path=stored_image.file_path,
                file_url=stored_image.file_url,
                width=stored_image.width,
                height=stored_image.height,
                status=ImageStatus.UPLOADED.value,
            )
            db.add(image_item)
            image_items.append(image_item)

        db.flush()

        db.commit()
        db.refresh(dataset)

        return DatasetUploadResponse(
            dataset_id=dataset.id,
            image_count=dataset.image_count,
            images=[
                ImageItemRead(
                    id=item.id,
                    dataset_id=item.dataset_id,
                    filename=item.filename,
                    file_path=item.file_path,
                    file_url=item.file_url,
                    width=item.width,
                    height=item.height,
                    status=item.status,
                    error_message=item.error_message,
                )
                for item in image_items
            ],
            warnings=warnings,
        )
    except Exception as exc:
        db.rollback()
        for path in images_dir.glob("*"):
            if path.is_file():
                path.unlink(missing_ok=True)
        if dataset_root.exists():
            try:
                images_dir.rmdir()
                dataset_root.rmdir()
            except OSError:
                logger.warning("Failed to clean up dataset directory after upload error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to persist dataset records: {exc}") from exc
