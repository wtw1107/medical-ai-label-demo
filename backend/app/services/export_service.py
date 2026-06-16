from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.converters.label_studio_parser import ParsedAnnotation, parse_human_annotation_task
from app.converters.mask_converter import write_mask_png
from app.core.config import Settings
from app.core.constants import ExportFormat, ExportRange, ExportRecordStatus, ImageStatus
from app.db.models import AnnotationTask, ExportRecord, ImageItem
from app.schemas.export import ExportRequest, ExportResponse, ExportStatusResponse
from app.services.label_studio_service import LabelStudioService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.label_studio_service = LabelStudioService(settings)

    def create_export(self, *, db: Session, task_id: str, payload: ExportRequest) -> ExportResponse:
        task = db.get(AnnotationTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Annotation task not found: {task_id}")
        if task.label_studio_project_id is None:
            raise HTTPException(status_code=400, detail="Label Studio project is not initialized for this task.")
        if payload.format not in {
            ExportFormat.LABEL_STUDIO_JSON.value,
            ExportFormat.SIMPLE_JSON.value,
            ExportFormat.MASK_PNG.value,
        }:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {payload.format}")
        if payload.range != ExportRange.CONFIRMED_ONLY.value:
            raise HTTPException(status_code=400, detail="MVP export currently supports confirmed_only only.")

        export_record = ExportRecord(
            task_id=task.id,
            format=payload.format,
            range=payload.range,
            status=ExportRecordStatus.RUNNING.value,
            created_by=self.settings.default_user_id,
            started_at=utc_now(),
        )
        db.add(export_record)
        db.flush()

        export_root = self.settings.ensure_data_root() / "exports" / export_record.id
        export_root.mkdir(parents=True, exist_ok=True)

        try:
            images = (
                db.query(ImageItem)
                .filter(ImageItem.dataset_id == task.dataset_id)
                .order_by(ImageItem.created_at.asc())
                .all()
            )
            self.label_studio_service.sync_project_task_mappings(db=db, task=task, images=images)
            remote_tasks = self.label_studio_service.get_project_task_lookup(task.label_studio_project_id)
            parsed_annotations = self._collect_confirmed_annotations(images=images, remote_tasks=remote_tasks)

            if not parsed_annotations:
                raise HTTPException(
                    status_code=400,
                    detail="No human annotations were found for this task. Please save at least one annotation in Label Studio.",
                )

            if payload.format == ExportFormat.LABEL_STUDIO_JSON.value:
                output_files = self._write_label_studio_json(export_root, remote_tasks, parsed_annotations)
            elif payload.format == ExportFormat.SIMPLE_JSON.value:
                output_files = self._write_simple_json(export_root, parsed_annotations)
            else:
                output_files = self._write_mask_png_bundle(export_root, parsed_annotations)

            zip_path = self._build_zip(export_record.id, export_root, output_files)
            export_record.status = ExportRecordStatus.COMPLETED.value
            export_record.total_count = len(parsed_annotations)
            export_record.file_path = str(zip_path)
            export_record.download_url = (
                f"{self.settings.media_base_url.rsplit('/media', 1)[0]}/api/exports/{export_record.id}/download"
            )
            export_record.finished_at = utc_now()
            export_record.error_message = None

            for image in images:
                if any(item.image_id == image.id for item in parsed_annotations):
                    image.status = ImageStatus.CONFIRMED.value
                    db.add(image)

            db.commit()
            db.refresh(export_record)
        except HTTPException as exc:
            db.rollback()
            self._mark_export_failed(db=db, export_record_id=export_record.id, message=str(exc.detail))
            raise
        except Exception as exc:
            db.rollback()
            self._mark_export_failed(db=db, export_record_id=export_record.id, message=str(exc))
            raise HTTPException(status_code=500, detail=f"Failed to export annotations: {exc}") from exc

        return ExportResponse(
            export_id=export_record.id,
            task_id=export_record.task_id,
            format=export_record.format,
            status=export_record.status,
            file_path=export_record.file_path or "",
            download_url=export_record.download_url or "",
        )

    def get_download_path(self, *, db: Session, export_id: str) -> Path:
        export_record = db.get(ExportRecord, export_id)
        if export_record is None:
            raise HTTPException(status_code=404, detail=f"Export record not found: {export_id}")
        if export_record.status != ExportRecordStatus.COMPLETED.value or not export_record.file_path:
            raise HTTPException(status_code=404, detail="Export file is not ready.")
        path = Path(export_record.file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Export zip file not found on disk.")
        return path

    def get_export_status(self, *, db: Session, export_id: str) -> ExportStatusResponse:
        export_record = db.get(ExportRecord, export_id)
        if export_record is None:
            raise HTTPException(status_code=404, detail=f"Export record not found: {export_id}")
        return ExportStatusResponse(
            export_id=export_record.id,
            task_id=export_record.task_id,
            format=export_record.format,
            range=export_record.range,
            status=export_record.status,
            file_path=export_record.file_path,
            download_url=export_record.download_url,
            total_count=export_record.total_count,
            error_message=export_record.error_message,
        )

    def _collect_confirmed_annotations(
        self,
        *,
        images: list[ImageItem],
        remote_tasks: dict[int, dict[str, object]],
    ) -> list[ParsedAnnotation]:
        parsed_annotations: list[ParsedAnnotation] = []
        for image in images:
            if image.label_studio_task_id is None or image.width is None or image.height is None:
                continue
            remote_task = remote_tasks.get(image.label_studio_task_id)
            if remote_task is None:
                continue
            parsed = parse_human_annotation_task(
                remote_task=remote_task,
                image_id=image.id,
                filename=image.filename,
                width=image.width,
                height=image.height,
            )
            if parsed is not None:
                parsed_annotations.append(parsed)
        return parsed_annotations

    def _write_label_studio_json(
        self,
        export_root: Path,
        remote_tasks: dict[int, dict[str, object]],
        parsed_annotations: list[ParsedAnnotation],
    ) -> list[Path]:
        parsed_by_task_id = {item.task_id: item for item in parsed_annotations}
        payload: list[dict[str, object]] = []
        for task_id, parsed in parsed_by_task_id.items():
            remote_task = remote_tasks.get(task_id)
            if not remote_task:
                continue
            annotations = remote_task.get("annotations", [])
            if not isinstance(annotations, list):
                continue
            human_annotation = next(
                (
                    item
                    for item in reversed(annotations)
                    if isinstance(item, dict)
                    and not item.get("was_cancelled", False)
                    and isinstance(item.get("result"), list)
                    and item.get("result")
                ),
                None,
            )
            if human_annotation is None:
                continue
            payload.append(
                {
                    "id": remote_task.get("id"),
                    "data": remote_task.get("data"),
                    "meta": remote_task.get("meta"),
                    "annotations": [human_annotation],
                    "image_id": parsed.image_id,
                    "filename": parsed.filename,
                }
            )
        output_path = export_root / "label_studio_annotations.json"
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return [output_path]

    def _write_simple_json(self, export_root: Path, parsed_annotations: list[ParsedAnnotation]) -> list[Path]:
        simple_records: list[dict[str, object]] = []
        for annotation in parsed_annotations:
            simple_records.append(
                {
                    "image_id": annotation.image_id,
                    "filename": annotation.filename,
                    "width": annotation.width,
                    "height": annotation.height,
                    "source": "human_confirmed",
                    "objects": [
                        {
                            "label": obj.label,
                            "bbox": obj.bbox,
                            "polygon": obj.polygon,
                            "source": obj.source,
                        }
                        for obj in annotation.objects
                    ],
                }
            )

        output_path = export_root / "annotations.simple.json"
        output_path.write_text(json.dumps(simple_records, ensure_ascii=False, indent=2), encoding="utf-8")
        return [output_path]

    def _write_mask_png_bundle(self, export_root: Path, parsed_annotations: list[ParsedAnnotation]) -> list[Path]:
        output_files: list[Path] = []
        manifest = []

        for annotation in parsed_annotations:
            mask_path = export_root / "masks" / f"{Path(annotation.filename).stem}.mask.png"
            write_mask_png(annotation, mask_path)
            output_files.append(mask_path)
            manifest.append(
                {
                    "image_id": annotation.image_id,
                    "filename": annotation.filename,
                    "mask_file": str(Path("masks") / mask_path.name).replace("\\", "/"),
                    "width": annotation.width,
                    "height": annotation.height,
                    "source": "human_confirmed",
                }
            )

        manifest_path = export_root / "masks.manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        output_files.append(manifest_path)
        return output_files

    def _build_zip(self, export_id: str, export_root: Path, output_files: list[Path]) -> Path:
        zip_path = export_root / f"{export_id}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for output_file in output_files:
                archive.write(output_file, arcname=output_file.relative_to(export_root))
        return zip_path

    def _mark_export_failed(self, *, db: Session, export_record_id: str, message: str) -> None:
        export_record = db.get(ExportRecord, export_record_id)
        if export_record is None:
            return
        export_record.status = ExportRecordStatus.FAILED.value
        export_record.error_message = message
        export_record.finished_at = utc_now()
        db.add(export_record)
        db.commit()
