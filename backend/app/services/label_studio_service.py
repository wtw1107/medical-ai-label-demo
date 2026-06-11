from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import AnnotationTaskStatus
from app.db.models import AnnotationTask, Dataset, ImageItem
from app.db.session import engine
from app.schemas.task import AnnotationTaskCreate, AnnotationTaskCreateResponse, AnnotationTaskUrlResponse


@dataclass
class LabelStudioProject:
    project_id: int
    project_url: str


def ensure_annotation_task_schema() -> None:
    with engine.begin() as connection:
        dialect = connection.dialect.name
        if dialect != "sqlite":
            return
        columns = connection.execute(text("PRAGMA table_info(annotation_tasks)")).mappings().all()
        if not columns:
            return
        column_names = {column["name"] for column in columns}
        if "label_studio_project_url" not in column_names:
            connection.execute(
                text("ALTER TABLE annotation_tasks ADD COLUMN label_studio_project_url VARCHAR(512)")
            )


class LabelStudioService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.label_studio_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.settings.label_studio_api_token:
            raise HTTPException(
                status_code=400,
                detail="LABEL_STUDIO_API_TOKEN is not configured. Please set it in .env before creating tasks.",
            )
        return {
            "Authorization": f"Token {self.settings.label_studio_api_token}",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, headers=self._headers(), timeout=30.0)

    def _project_url(self, project_id: int) -> str:
        return f"{self.base_url}/projects/{project_id}/data"

    def _load_label_config(self, task_type: str) -> str:
        try:
            path = self.settings.get_label_config_path(task_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.exists():
            raise HTTPException(status_code=500, detail=f"Label config file not found: {path}")
        return path.read_text(encoding="utf-8")

    def _build_tasks_payload(self, dataset: Dataset, images: list[ImageItem]) -> list[dict[str, object]]:
        tasks: list[dict[str, object]] = []
        for image in images:
            tasks.append(
                {
                    "data": {
                        "image": image.file_url,
                    },
                    "meta": {
                        "image_id": image.id,
                        "dataset_id": dataset.id,
                        "filename": image.filename,
                    },
                }
            )
        return tasks

    def create_project(self, *, title: str, description: str | None, task_type: str) -> LabelStudioProject:
        label_config = self._load_label_config(task_type)
        payload = {
            "title": title,
            "description": description,
            "label_config": label_config,
        }
        try:
            with self._client() as client:
                response = client.post("/api/projects", json=payload)
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=503,
                detail="Could not connect to Label Studio. Please make sure Label Studio is running.",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Label Studio request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail="Label Studio authentication failed. Please check LABEL_STUDIO_API_TOKEN.",
            )
        if response.is_error:
            raise HTTPException(
                status_code=502,
                detail=f"Label Studio project creation failed: {response.text}",
            )

        body = response.json()
        project_id = body.get("id")
        if not isinstance(project_id, int):
            raise HTTPException(status_code=502, detail="Label Studio did not return a valid project ID.")
        return LabelStudioProject(project_id=project_id, project_url=self._project_url(project_id))

    def import_tasks(self, *, project_id: int, tasks: list[dict[str, object]]) -> None:
        try:
            with self._client() as client:
                response = client.post(f"/api/projects/{project_id}/import", json=tasks)
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=503,
                detail="Could not connect to Label Studio while importing tasks.",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Label Studio import request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail="Label Studio authentication failed during task import. Please check LABEL_STUDIO_API_TOKEN.",
            )
        if response.is_error:
            raise HTTPException(
                status_code=502,
                detail=f"Label Studio task import failed: {response.text}",
            )

        body = response.json()
        import_id = body.get("import")
        task_count = body.get("task_count")
        if isinstance(task_count, int):
            return
        if isinstance(import_id, int):
            self._wait_for_import(project_id=project_id, import_id=import_id)

    def _wait_for_import(self, *, project_id: int, import_id: int) -> None:
        with self._client() as client:
            for _ in range(10):
                response = client.get(f"/api/projects/{project_id}/imports/{import_id}")
                if response.is_error:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Label Studio import status check failed: {response.text}",
                    )
                body = response.json()
                status = body.get("status")
                if status == "completed":
                    return
                if status == "failed":
                    error_message = body.get("error") or "Label Studio import failed."
                    raise HTTPException(status_code=502, detail=str(error_message))
                time.sleep(0.5)
        raise HTTPException(status_code=504, detail="Timed out waiting for Label Studio task import to complete.")

    def create_annotation_task(
        self,
        *,
        db: Session,
        payload: AnnotationTaskCreate,
    ) -> AnnotationTaskCreateResponse:
        dataset = db.get(Dataset, payload.dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {payload.dataset_id}")

        images = (
            db.query(ImageItem)
            .filter(ImageItem.dataset_id == payload.dataset_id)
            .order_by(ImageItem.created_at.asc())
            .all()
        )
        if not images:
            raise HTTPException(status_code=400, detail="Dataset contains no images to import into Label Studio.")

        task_record = AnnotationTask(
            dataset_id=payload.dataset_id,
            name=payload.name,
            task_type=payload.task_type,
            label_name=payload.label_name,
            det_model_id=payload.det_model_id,
            seg_model_id=payload.seg_model_id,
            require_human_confirm=payload.require_human_confirm,
            status=AnnotationTaskStatus.CREATED.value,
        )
        db.add(task_record)
        db.flush()

        try:
            project = self.create_project(
                title=payload.name,
                description=f"Dataset: {dataset.name}",
                task_type=payload.task_type,
            )
            self.import_tasks(
                project_id=project.project_id,
                tasks=self._build_tasks_payload(dataset, images),
            )
            task_record.label_studio_project_id = project.project_id
            task_record.label_studio_project_url = project.project_url
            task_record.status = AnnotationTaskStatus.REVIEWING.value
            task_record.error_message = None
            db.commit()
            db.refresh(task_record)
        except HTTPException as exc:
            task_record.status = AnnotationTaskStatus.ERROR.value
            task_record.error_message = str(exc.detail)
            db.commit()
            raise
        except Exception as exc:
            task_record.status = AnnotationTaskStatus.ERROR.value
            task_record.error_message = str(exc)
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to create annotation task: {exc}") from exc

        return AnnotationTaskCreateResponse(
            task_id=task_record.id,
            dataset_id=task_record.dataset_id,
            label_studio_project_id=task_record.label_studio_project_id or 0,
            label_studio_project_url=task_record.label_studio_project_url or "",
            status=task_record.status,
        )

    def get_label_studio_url(self, *, db: Session, task_id: str) -> AnnotationTaskUrlResponse:
        task = db.get(AnnotationTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Annotation task not found: {task_id}")
        if not task.label_studio_project_url:
            raise HTTPException(
                status_code=404,
                detail="Label Studio project URL is not available for this task.",
            )
        return AnnotationTaskUrlResponse(url=task.label_studio_project_url)
