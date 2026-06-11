from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    AnnotationTaskStatus,
    DataType,
    DatasetStatus,
    ExportFormat,
    ExportRange,
    ExportRecordStatus,
    ImageStatus,
    PrelabelJobStatus,
    TaskType,
)
from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Dataset(Base, TimestampMixin):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(32), default=DataType.IMAGE.value, nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    root_dir: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=DatasetStatus.UPLOADED.value, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    image_items: Mapped[list[ImageItem]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    annotation_tasks: Mapped[list[AnnotationTask]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class ImageItem(Base, TimestampMixin):
    __tablename__ = "image_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    dataset_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ImageStatus.UPLOADED.value, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="image_items")


class AnnotationTask(Base, TimestampMixin):
    __tablename__ = "annotation_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    dataset_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), default=TaskType.BBOX.value, nullable=False)
    label_name: Mapped[str] = mapped_column(String(128), nullable=False)
    det_model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seg_model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    require_human_confirm: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    label_studio_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=AnnotationTaskStatus.CREATED.value,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="annotation_tasks")
    prelabel_jobs: Mapped[list[PrelabelJob]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    export_records: Mapped[list[ExportRecord]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class PrelabelJob(Base, TimestampMixin):
    __tablename__ = "prelabel_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    task_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("annotation_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=PrelabelJobStatus.PENDING.value,
        nullable=False,
    )
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_confirm: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped[AnnotationTask] = relationship(back_populates="prelabel_jobs")


class ExportRecord(Base, TimestampMixin):
    __tablename__ = "export_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    task_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("annotation_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(String(32), default=ExportFormat.LABEL_STUDIO_JSON.value, nullable=False)
    range: Mapped[str] = mapped_column(String(32), default=ExportRange.CONFIRMED_ONLY.value, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ExportRecordStatus.PENDING.value,
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    download_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    task: Mapped[AnnotationTask] = relationship(back_populates="export_records")
