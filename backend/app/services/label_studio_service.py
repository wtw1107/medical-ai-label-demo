from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import AnnotationTaskStatus, ImageStatus
from app.db.models import AnnotationTask, Dataset, ImageItem
from app.db.session import engine
from app.schemas.task import (
    AnnotationTaskCreate,
    AnnotationTaskCreateResponse,
    AnnotationTaskDetailResponse,
    AnnotationTaskListItemResponse,
    AnnotationTaskListResponse,
    AnnotationTaskUrlResponse,
)


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
        image_columns = connection.execute(text("PRAGMA table_info(image_items)")).mappings().all()
        image_column_names = {column["name"] for column in image_columns}
        if "label_studio_task_id" not in image_column_names:
            connection.execute(text("ALTER TABLE image_items ADD COLUMN label_studio_task_id INTEGER"))


class LabelStudioService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.label_studio_url.rstrip("/")

    def _refresh_access_token(self) -> str:
        if not self.settings.label_studio_api_token:
            raise HTTPException(
                status_code=400,
                detail="LABEL_STUDIO_API_TOKEN is not configured. Please set it in .env before creating tasks.",
            )

        refresh_url = f"{self.base_url}/api/token/refresh/"
        payload = {"refresh": self.settings.label_studio_api_token}

        try:
            response = httpx.post(refresh_url, json=payload, timeout=30.0, trust_env=False)
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=503,
                detail="Could not connect to Label Studio. Please make sure Label Studio is running.",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Label Studio token refresh request failed: {exc}") from exc

        if response.is_error:
            raise HTTPException(
                status_code=502,
                detail="Failed to refresh Label Studio access token. Please check LABEL_STUDIO_API_TOKEN.",
            )

        access_token = response.json().get("access")
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=502,
                detail="Failed to refresh Label Studio access token. Please check LABEL_STUDIO_API_TOKEN.",
            )
        return access_token

    def _headers(self) -> dict[str, str]:
        access_token = self._refresh_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=30.0,
            trust_env=False,
        )

    def _format_error_response(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            return response.text

        if isinstance(body, dict):
            validation_errors = body.get("validation_errors")
            if isinstance(validation_errors, dict):
                messages: list[str] = []
                for field, field_errors in validation_errors.items():
                    if not isinstance(field_errors, list):
                        continue
                    for field_error in field_errors:
                        if isinstance(field_error, str):
                            messages.append(f"{field}: {field_error}")
                if messages:
                    return "; ".join(messages)

            detail = body.get("detail")
            if isinstance(detail, str) and detail:
                return detail

        return response.text

    def _project_url(self, project_id: int) -> str:
        return f"{self.base_url}/projects/{project_id}/data"

    def build_task_url(self, project_url: str | None, label_studio_task_id: int | None) -> str | None:
        if not project_url or label_studio_task_id is None:
            return None
        return f"{project_url}?task={label_studio_task_id}"

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

    def _request(
        self,
        *,
        method: str,
        path: str,
        json: dict[str, object] | list[dict[str, object]] | None = None,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            with self._client() as client:
                response = client.request(method, path, json=json, params=params)
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
                detail="Failed to refresh Label Studio access token. Please check LABEL_STUDIO_API_TOKEN.",
            )
        if response.is_error:
            raise HTTPException(
                status_code=502,
                detail=f"Label Studio request failed: {self._format_error_response(response)}",
            )

        body = response.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=502, detail="Label Studio returned an invalid response payload.")
        return body

    def create_project(self, *, title: str, description: str | None, task_type: str) -> LabelStudioProject:
        label_config = self._load_label_config(task_type)
        normalized_title = title.strip()
        payload = {
            "title": normalized_title,
            "description": description,
            "label_config": label_config,
        }
        body = self._request(method="POST", path="/api/projects", json=payload)
        project_id = body.get("id")
        if not isinstance(project_id, int):
            raise HTTPException(status_code=502, detail="Label Studio did not return a valid project ID.")
        return LabelStudioProject(project_id=project_id, project_url=self._project_url(project_id))

    def import_tasks(self, *, project_id: int, tasks: list[dict[str, object]]) -> None:
        body = self._request(
            method="POST",
            path=f"/api/projects/{project_id}/import",
            json=tasks,
        )
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

    def list_project_tasks(self, project_id: int) -> list[dict[str, object]]:
        tasks: list[dict[str, object]] = []
        page = 1
        page_size = 100

        while True:
            body = self._request(
                method="GET",
                path="/api/tasks",
                params={
                    "project": project_id,
                    "fields": "all",
                    "page": page,
                    "page_size": page_size,
                },
            )
            chunk = body.get("tasks", [])
            if not isinstance(chunk, list):
                raise HTTPException(status_code=502, detail="Label Studio returned an invalid task list payload.")
            tasks.extend(item for item in chunk if isinstance(item, dict))
            if len(chunk) < page_size:
                break
            page += 1

        return tasks

    def sync_project_task_mappings(
        self,
        *,
        db: Session,
        task: AnnotationTask,
        images: list[ImageItem] | None = None,
    ) -> None:
        if task.label_studio_project_id is None:
            raise HTTPException(status_code=400, detail="Label Studio project is not initialized for this task.")

        if images is None:
            images = (
                db.query(ImageItem)
                .filter(ImageItem.dataset_id == task.dataset_id)
                .order_by(ImageItem.created_at.asc())
                .all()
            )

        image_map = {image.id: image for image in images}
        for remote_task in self.list_project_tasks(task.label_studio_project_id):
            remote_task_id = remote_task.get("id")
            meta = remote_task.get("meta", {})
            if not isinstance(remote_task_id, int) or not isinstance(meta, dict):
                continue
            image_id = meta.get("image_id")
            image = image_map.get(image_id)
            if image is not None:
                image.label_studio_task_id = remote_task_id
                db.add(image)

    def get_project_task_lookup(self, project_id: int) -> dict[int, dict[str, object]]:
        lookup: dict[int, dict[str, object]] = {}
        for remote_task in self.list_project_tasks(project_id):
            remote_task_id = remote_task.get("id")
            if isinstance(remote_task_id, int):
                lookup[remote_task_id] = remote_task
        return lookup

    def create_prediction(
        self,
        *,
        project_id: int,
        label_studio_task_id: int,
        model_version: str,
        score: float,
        results: list[dict[str, object]],
    ) -> dict[str, object]:
        return self._request(
            method="POST",
            path="/api/predictions",
            json={
                "project": project_id,
                "task": label_studio_task_id,
                "model_version": model_version,
                "score": score,
                "result": results,
            },
        )

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
            self.sync_project_task_mappings(db=db, task=task_record, images=images)
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

    def get_annotation_task(self, *, db: Session, task_id: str) -> AnnotationTaskDetailResponse:
        task = db.get(AnnotationTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Annotation task not found: {task_id}")
        return AnnotationTaskDetailResponse(
            task_id=task.id,
            dataset_id=task.dataset_id,
            name=task.name,
            task_type=task.task_type,
            label_name=task.label_name,
            det_model_id=task.det_model_id,
            seg_model_id=task.seg_model_id,
            require_human_confirm=task.require_human_confirm,
            label_studio_project_id=task.label_studio_project_id,
            label_studio_project_url=task.label_studio_project_url,
            status=task.status,
            error_message=task.error_message,
        )

    def list_annotation_tasks(self, *, db: Session) -> AnnotationTaskListResponse:
        tasks = db.query(AnnotationTask).order_by(AnnotationTask.created_at.desc()).all()
        items: list[AnnotationTaskListItemResponse] = []

        for task in tasks:
            dataset = db.get(Dataset, task.dataset_id)
            image_items = (
                db.query(ImageItem)
                .filter(ImageItem.dataset_id == task.dataset_id)
                .order_by(ImageItem.created_at.asc())
                .all()
            )
            prediction_written_count = sum(
                1 for image in image_items if image.status == ImageStatus.PRELABEL_DONE.value
            )
            items.append(
                AnnotationTaskListItemResponse(
                    task_id=task.id,
                    task_name=task.name,
                    task_type=task.task_type,
                    dataset_id=task.dataset_id,
                    dataset_name=dataset.name if dataset is not None else None,
                    image_count=dataset.image_count if dataset is not None else len(image_items),
                    prediction_written_count=prediction_written_count,
                    annotation_saved_count=0,
                    label_studio_project_id=task.label_studio_project_id,
                    label_studio_project_url=task.label_studio_project_url,
                    created_at=task.created_at.isoformat(),
                    updated_at=task.updated_at.isoformat(),
                    status=task.status,
                )
            )

        return AnnotationTaskListResponse(items=items, total=len(items))
