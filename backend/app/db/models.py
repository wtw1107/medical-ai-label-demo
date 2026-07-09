from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    AnnotationTaskStatus,
    BLineGrade,
    DataType,
    DatasetSplit,
    DeidentificationStatus,
    DatasetStatus,
    ExportFormat,
    ExportRange,
    ExportRecordStatus,
    ImageStatus,
    KeyFrameReviewStatus,
    KeyFrameReason,
    PrelabelJobStatus,
    TaskType,
    VideoAnnotationStatus,
    VideoItemStatus,
    VideoQuality,
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
    patients: Mapped[list[Patient]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    video_items: Mapped[list[VideoItem]] = relationship(
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
    label_studio_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ImageStatus.UPLOADED.value, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="image_items")


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    dataset_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_uid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    split: Mapped[str] = mapped_column(
        String(32),
        default=DatasetSplit.UNASSIGNED.value,
        nullable=False,
    )
    site: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_group: Mapped[str | None] = mapped_column(String(128), nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="patients")
    video_items: Mapped[list[VideoItem]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )


class VideoItem(Base, TimestampMixin):
    __tablename__ = "video_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    dataset_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    duration_sec: Mapped[float | None] = mapped_column(nullable=True)
    fps: Mapped[float | None] = mapped_column(nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preview_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    preview_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    lung_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    probe: Mapped[str | None] = mapped_column(String(64), nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device: Mapped[str | None] = mapped_column(String(128), nullable=True)
    depth: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deid_status: Mapped[str] = mapped_column(
        String(32),
        default=DeidentificationStatus.UNKNOWN.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=VideoItemStatus.UPLOADED.value,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="video_items")
    patient: Mapped[Patient | None] = relationship(back_populates="video_items")
    reviews: Mapped[list[VideoReview]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )
    keyframes: Mapped[list[KeyFrame]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )


class VideoReview(Base, TimestampMixin):
    __tablename__ = "video_reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    video_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("video_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quality: Mapped[str] = mapped_column(
        String(32),
        default=VideoQuality.UNKNOWN.value,
        nullable=False,
    )
    bline_grade: Mapped[str] = mapped_column(
        String(32),
        default=BLineGrade.UNKNOWN.value,
        nullable=False,
    )
    uncertain_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    include_in_training: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    video: Mapped[VideoItem] = relationship(back_populates="reviews")


class KeyFrame(Base, TimestampMixin):
    __tablename__ = "key_frames"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    video_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("video_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    selection_reason: Mapped[str] = mapped_column(
        String(32),
        default=KeyFrameReason.MANUAL.value,
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    annotation_status: Mapped[str] = mapped_column(
        String(32),
        default=VideoAnnotationStatus.PENDING.value,
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String(32),
        default=KeyFrameReviewStatus.UNREVIEWED.value,
        nullable=False,
    )

    video: Mapped[VideoItem] = relationship(back_populates="keyframes")


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
    label_studio_project_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
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
