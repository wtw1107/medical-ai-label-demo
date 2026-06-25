from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.converters.label_studio_prediction_converter import build_prediction_bundle
from app.core.config import Settings
from app.core.constants import (
    AnnotationStatus,
    AnnotationTaskStatus,
    ImageStatus,
    PredictionStatus,
    PrelabelJobStatus,
    TaskType,
)
from app.db.models import AnnotationTask, ImageItem, PrelabelJob
from app.schemas.prelabel import (
    LabelStudioStatusSyncResponse,
    PredictionPreviewItem,
    PredictionPreviewResponse,
    PredictionPreviewValue,
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
        task, image_statuses = self._collect_task_image_statuses(db=db, task_id=task_id)
        return TaskImageStatusResponse(task_id=task.id, images=image_statuses)

    def sync_label_studio_status(self, *, db: Session, task_id: str) -> LabelStudioStatusSyncResponse:
        task, image_statuses = self._collect_task_image_statuses(db=db, task_id=task_id)
        prediction_written_count = sum(1 for image in image_statuses if image.prediction_status == PredictionStatus.WRITTEN.value)
        annotation_saved_count = sum(1 for image in image_statuses if image.annotation_status == AnnotationStatus.SAVED.value)
        return LabelStudioStatusSyncResponse(
            task_id=task.id,
            synced_count=len(image_statuses),
            prediction_written_count=prediction_written_count,
            annotation_saved_count=annotation_saved_count,
            images=image_statuses,
        )

    def get_prediction_preview(
        self,
        *,
        db: Session,
        task_id: str,
        image_id: str,
    ) -> PredictionPreviewResponse:
        task = db.get(AnnotationTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Annotation task not found: {task_id}")
        if task.label_studio_project_id is None:
            raise HTTPException(status_code=400, detail="Label Studio project is not initialized for this task.")

        image = db.get(ImageItem, image_id)
        if image is None or image.dataset_id != task.dataset_id:
            raise HTTPException(status_code=404, detail=f"Image not found in task dataset: {image_id}")

        self.label_studio_service.sync_project_task_mappings(db=db, task=task, images=[image])
        db.flush()

        if image.label_studio_task_id is None:
            db.commit()
            return PredictionPreviewResponse(
                task_id=task.id,
                image_id=image.id,
                filename=image.filename,
                image_url=image.file_url,
                image_width=image.width,
                image_height=image.height,
                label_studio_task_id=None,
                label_studio_task_url=None,
                has_prediction=False,
                model_version=None,
                predictions=[],
                raw_prediction_count=0,
            )

        remote_tasks = self.label_studio_service.get_project_task_lookup(task.label_studio_project_id)
        remote_task = remote_tasks.get(image.label_studio_task_id)
        predictions_payload = remote_task.get("predictions", []) if isinstance(remote_task, dict) else []
        predictions = predictions_payload if isinstance(predictions_payload, list) else []

        preview_items: list[PredictionPreviewItem] = []
        latest_model_version: str | None = None
        if predictions:
            latest_prediction = predictions[-1] if isinstance(predictions[-1], dict) else None
            if latest_prediction is not None:
                latest_model_version = latest_prediction.get("model_version")

            for prediction in predictions:
                if not isinstance(prediction, dict):
                    continue
                result_items = prediction.get("result", [])
                if not isinstance(result_items, list):
                    continue
                for result_item in result_items:
                    parsed_item = self._parse_prediction_result(result_item)
                    if parsed_item is not None:
                        preview_items.append(parsed_item)

        db.commit()
        return PredictionPreviewResponse(
            task_id=task.id,
            image_id=image.id,
            filename=image.filename,
            image_url=image.file_url,
            image_width=image.width,
            image_height=image.height,
            label_studio_task_id=image.label_studio_task_id,
            label_studio_task_url=self.label_studio_service.build_task_url(
                task.label_studio_project_url,
                image.label_studio_task_id,
            ),
            has_prediction=bool(preview_items),
            model_version=latest_model_version,
            predictions=preview_items,
            raw_prediction_count=len(predictions),
        )

    def _collect_task_image_statuses(
        self,
        *,
        db: Session,
        task_id: str,
    ) -> tuple[AnnotationTask, list[TaskImageStatusItem]]:
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
            prediction_status = self._prediction_status(image=image, has_prediction=has_prediction)
            annotation_status = AnnotationStatus.SAVED.value if has_annotation else AnnotationStatus.UNSAVED.value
            image_statuses.append(
                TaskImageStatusItem(
                    image_id=image.id,
                    filename=image.filename,
                    status=image.status,
                    has_prediction=has_prediction,
                    has_annotation=has_annotation,
                    prediction_status=prediction_status,
                    annotation_status=annotation_status,
                    label_studio_task_id=image.label_studio_task_id,
                    label_studio_task_url=self.label_studio_service.build_task_url(
                        task.label_studio_project_url,
                        image.label_studio_task_id,
                    ),
                )
            )

        db.commit()
        return task, image_statuses

    def _prediction_status(self, *, image: ImageItem, has_prediction: bool) -> str:
        if has_prediction:
            return PredictionStatus.WRITTEN.value
        if image.status == ImageStatus.PRELABEL_FAILED.value:
            return PredictionStatus.FAILED.value
        return PredictionStatus.NONE.value

    def _parse_prediction_result(self, result_item: object) -> PredictionPreviewItem | None:
        if not isinstance(result_item, dict):
            return None

        prediction_type = result_item.get("type")
        value = result_item.get("value")
        if not isinstance(prediction_type, str) or not isinstance(value, dict):
            return None
        if prediction_type not in {"rectanglelabels", "polygonlabels"}:
            return None

        score = result_item.get("score")
        normalized_score = float(score) if isinstance(score, (int, float)) else None

        if prediction_type == "rectanglelabels":
            labels = value.get("rectanglelabels", [])
            label = labels[0] if isinstance(labels, list) and labels else "unknown"
            return PredictionPreviewItem(
                type=prediction_type,
                label=label,
                score=normalized_score,
                value=PredictionPreviewValue(
                    x=self._safe_float(value.get("x")),
                    y=self._safe_float(value.get("y")),
                    width=self._safe_float(value.get("width")),
                    height=self._safe_float(value.get("height")),
                ),
            )

        labels = value.get("polygonlabels", [])
        label = labels[0] if isinstance(labels, list) and labels else "unknown"
        points = value.get("points", [])
        normalized_points = []
        if isinstance(points, list):
            for point in points:
                if (
                    isinstance(point, list)
                    and len(point) == 2
                    and isinstance(point[0], (int, float))
                    and isinstance(point[1], (int, float))
                ):
                    normalized_points.append([float(point[0]), float(point[1])])
        return PredictionPreviewItem(
            type=prediction_type,
            label=label,
            score=normalized_score,
            value=PredictionPreviewValue(points=normalized_points),
        )

    def _safe_float(self, value: object) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        return None

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
