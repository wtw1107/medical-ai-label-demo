from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.converters.label_studio_prediction_converter import build_prediction_bundle
from app.core.config import Settings
from app.core.constants import AnnotationTaskStatus, ImageStatus, PrelabelJobStatus, TaskType
from app.db.models import AnnotationTask, ImageItem, PrelabelJob
from app.schemas.prelabel import (
    PrelabelJobStatusResponse,
    PrelabelRunResponse,
    TaskImageStatusItem,
    TaskImageStatusResponse,
)
from app.services.label_studio_service import LabelStudioService
from app.services.model_service import ModelServiceClient


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PrelabelService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_client = ModelServiceClient(settings)
        self.label_studio_service = LabelStudioService(settings)

    def run_prelabel(self, *, db: Session, task_id: str) -> PrelabelRunResponse:
        task = db.get(AnnotationTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Annotation task not found: {task_id}")
        if task.label_studio_project_id is None:
            raise HTTPException(status_code=400, detail="Label Studio project is not initialized for this task.")

        images = (
            db.query(ImageItem)
            .filter(ImageItem.dataset_id == task.dataset_id)
            .order_by(ImageItem.created_at.asc())
            .all()
        )
        if not images:
            raise HTTPException(status_code=400, detail="No images found for this annotation task.")

        task.status = AnnotationTaskStatus.PRELABELING.value
        job = PrelabelJob(
            task_id=task.id,
            status=PrelabelJobStatus.RUNNING.value,
            total_count=len(images),
            success_count=0,
            failed_count=0,
            pending_confirm=0,
            started_at=utc_now(),
        )
        db.add(job)
        db.flush()

        self.label_studio_service.sync_project_task_mappings(
            db=db,
            task=task,
            images=images,
        )
        db.flush()

        for image in images:
            image.status = ImageStatus.PRELABELING.value
            image.error_message = None

        db.commit()
        db.refresh(job)

        try:
            success_count = 0
            failed_count = 0

            for image in images:
                try:
                    if image.width is None or image.height is None:
                        raise ValueError("Image width/height is missing.")
                    if image.label_studio_task_id is None:
                        raise ValueError("Label Studio task mapping is missing for this image.")

                    detection, segmentation = self._predict_for_image(task=task, image=image)
                    bundle = build_prediction_bundle(
                        task_type=task.task_type,
                        label_name=task.label_name,
                        image_width=image.width,
                        image_height=image.height,
                        detection=detection,
                        segmentation=segmentation,
                    )
                    self.label_studio_service.create_prediction(
                        project_id=task.label_studio_project_id,
                        label_studio_task_id=image.label_studio_task_id,
                        model_version=bundle.model_version,
                        score=bundle.score,
                        results=bundle.results,
                    )
                    image.status = ImageStatus.PRELABEL_DONE.value
                    image.error_message = None
                    success_count += 1
                except Exception as exc:
                    image.status = ImageStatus.PRELABEL_FAILED.value
                    image.error_message = str(getattr(exc, "detail", exc))
                    failed_count += 1
                finally:
                    db.add(image)
                    db.flush()

            job.success_count = success_count
            job.failed_count = failed_count
            job.pending_confirm = success_count if task.require_human_confirm else 0
            job.finished_at = utc_now()

            if success_count == 0:
                job.status = PrelabelJobStatus.FAILED.value
                task.status = AnnotationTaskStatus.ERROR.value
                job.error_message = "All images failed during prelabel."
                task.error_message = job.error_message
            elif failed_count > 0:
                job.status = PrelabelJobStatus.PARTIAL_FAILED.value
                task.status = AnnotationTaskStatus.REVIEWING.value
                job.error_message = f"{failed_count} image(s) failed during prelabel."
                task.error_message = job.error_message
            else:
                job.status = PrelabelJobStatus.COMPLETED.value
                task.status = AnnotationTaskStatus.REVIEWING.value
                job.error_message = None
                task.error_message = None

            db.commit()
            db.refresh(job)
        except Exception:
            db.rollback()
            raise

        return PrelabelRunResponse(
            job_id=job.id,
            task_id=job.task_id,
            status=job.status,
            total_count=job.total_count,
            success_count=job.success_count,
            failed_count=job.failed_count,
        )

    def get_prelabel_job(self, *, db: Session, job_id: str) -> PrelabelJobStatusResponse:
        job = db.get(PrelabelJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Prelabel job not found: {job_id}")

        return PrelabelJobStatusResponse(
            job_id=job.id,
            task_id=job.task_id,
            status=job.status,
            total_count=job.total_count,
            success_count=job.success_count,
            failed_count=job.failed_count,
            error_message=job.error_message,
        )

    def list_task_images(self, *, db: Session, task_id: str) -> TaskImageStatusResponse:
        task = db.get(AnnotationTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Annotation task not found: {task_id}")

        images = (
            db.query(ImageItem)
            .filter(ImageItem.dataset_id == task.dataset_id)
            .order_by(ImageItem.created_at.asc())
            .all()
        )
        if task.label_studio_project_id is None:
            raise HTTPException(status_code=400, detail="Label Studio project is not initialized for this task.")

        self.label_studio_service.sync_project_task_mappings(db=db, task=task, images=images)
        remote_tasks = self.label_studio_service.get_project_task_lookup(task.label_studio_project_id)

        image_statuses: list[TaskImageStatusItem] = []
        for image in images:
            remote_task = remote_tasks.get(image.label_studio_task_id or -1)
            has_prediction = bool(remote_task and remote_task.get("total_predictions", 0) > 0)
            has_annotation = bool(remote_task and remote_task.get("total_annotations", 0) > 0)
            image_statuses.append(
                TaskImageStatusItem(
                    image_id=image.id,
                    filename=image.filename,
                    status=image.status,
                    has_prediction=has_prediction,
                    has_annotation=has_annotation,
                )
            )

        db.commit()
        return TaskImageStatusResponse(task_id=task.id, images=image_statuses)

    def _predict_for_image(
        self,
        *,
        task: AnnotationTask,
        image: ImageItem,
    ) -> tuple[dict[str, object] | None, dict[str, object] | None]:
        detection: dict[str, object] | None = None
        segmentation: dict[str, object] | None = None

        if task.task_type in {TaskType.BBOX.value, TaskType.BBOX_POLYGON.value}:
            detection = self.model_client.predict_detection(
                image_url=image.file_url,
                image_id=image.id,
                model_id=task.det_model_id or "mock_detection",
            )

        if task.task_type == TaskType.POLYGON.value:
            segmentation = self.model_client.predict_segmentation(
                image_url=image.file_url,
                image_id=image.id,
                model_id=task.seg_model_id or "mock_segmentation",
            )
        elif task.task_type == TaskType.BBOX_POLYGON.value:
            if not detection or not detection.get("results"):
                raise ValueError("Detection results are missing for bbox_polygon prelabel.")
            bbox_prompt = detection["results"][0]["bbox"]
            segmentation = self.model_client.predict_segmentation(
                image_url=image.file_url,
                image_id=image.id,
                model_id=task.seg_model_id or "mock_segmentation",
                bbox_prompt=bbox_prompt,
            )

        return detection, segmentation
