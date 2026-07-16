from __future__ import annotations

import time
import csv
import json
import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import DataType
from app.db.models import Dataset, VideoItem
from app.schemas.video import (
    CvatAnnotationSummaryResponse,
    CvatHealthResponse,
    CvatInitResponse,
    CvatSyncResponse,
    CvatVideoMappingItem,
    VideoKeyframeExportResponse,
)


REQUEST_TIMEOUT_SECONDS = 600


@dataclass
class CvatExportRecord:
    dataset_id: str
    video_id: str
    cvat_project_id: int | None
    cvat_task_id: int | None
    cvat_job_id: int | None
    patient_uid: str | None
    lung_zone: str | None
    filename: str
    frame_index: int
    timestamp_ms: int
    selection_reason: str
    annotation_result: str
    image_path: str
    mask_path: str
    mask_type: str
    review_status: str | None
    issue_count: int


class CvatService:
    """Project-side CVAT integration for the local video B-line spike."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.cvat_url.rstrip("/")

    def health(self) -> CvatHealthResponse:
        if not self.base_url:
            return CvatHealthResponse(
                configured=False,
                reachable=False,
                authenticated=False,
                error="CVAT_URL is not configured.",
            )

        try:
            with self._client(authenticated=False) as client:
                about = client.get("/api/server/about")
                about.raise_for_status()
                server_payload = about.json()
        except httpx.HTTPError as exc:
            return CvatHealthResponse(
                configured=True,
                reachable=False,
                authenticated=False,
                error=f"Could not reach CVAT at {self.base_url}: {exc}",
            )

        try:
            with self._client(authenticated=True) as client:
                user = client.get("/api/users/self")
                user.raise_for_status()
                issue_supported = self._endpoint_available(client, "/api/issues")
                jobs = client.get("/api/jobs", params={"page_size": 1})
                review_supported = jobs.status_code < 500 and "stage" in jobs.text
                plugins = client.get("/api/server/plugins")
                consensus_supported = "consensus" in plugins.text.lower() if plugins.status_code == 200 else None
        except httpx.HTTPStatusError as exc:
            return CvatHealthResponse(
                configured=True,
                reachable=True,
                authenticated=False,
                server_version=str(server_payload.get("version")) if server_payload.get("version") else None,
                error=f"CVAT authentication failed with HTTP {exc.response.status_code}.",
            )
        except httpx.HTTPError as exc:
            return CvatHealthResponse(
                configured=True,
                reachable=True,
                authenticated=False,
                server_version=str(server_payload.get("version")) if server_payload.get("version") else None,
                error=f"CVAT authentication request failed: {exc}",
            )

        version = server_payload.get("version") or server_payload.get("server_version")
        return CvatHealthResponse(
            configured=True,
            reachable=True,
            authenticated=True,
            server_version=str(version) if version is not None else None,
            review_supported=review_supported,
            issue_supported=issue_supported,
            consensus_supported=consensus_supported,
            error=None,
        )

    def init_dataset(self, *, db: Session, dataset_id: str) -> CvatInitResponse:
        dataset = self._get_video_dataset(db=db, dataset_id=dataset_id)
        videos = self._list_videos(db=db, dataset_id=dataset.id)
        health = self.health()
        if not health.reachable or not health.authenticated:
            return CvatInitResponse(
                dataset_id=dataset.id,
                cvat_project_id=dataset.cvat_project_id,
                cvat_project_url=dataset.cvat_project_url,
                created_task_count=0,
                reused_task_count=sum(1 for item in videos if item.cvat_task_id is not None),
                videos=[self._mapping_item(item, error=health.error) for item in videos],
                error=health.error or "CVAT is not reachable or authenticated.",
            )

        created_count = 0
        reused_count = 0
        errors: list[str] = []
        mappings: list[CvatVideoMappingItem] = []

        with self._client(authenticated=True) as client:
            if dataset.cvat_project_id is None:
                project = self._create_project(client, dataset)
                dataset.cvat_project_id = int(project["id"])
                dataset.cvat_project_url = self._build_project_url(dataset.cvat_project_id)
                dataset.annotation_backend = "cvat"
                db.add(dataset)
                db.commit()
                db.refresh(dataset)

            for video in videos:
                if video.cvat_task_id is not None:
                    reused_count += 1
                    self._refresh_video_mapping(client=client, db=db, video=video)
                    mappings.append(self._mapping_item(video))
                    continue

                try:
                    task = self._create_task(client=client, dataset=dataset, video=video)
                    video.cvat_task_id = int(task["id"])
                    video.cvat_task_url = self._build_task_url(video.cvat_task_id)
                    video.cvat_status = "uploading"
                    db.add(video)
                    db.commit()
                    db.refresh(video)

                    self._upload_video_to_task(client=client, video=video)
                    self._refresh_video_mapping(client=client, db=db, video=video)
                    created_count += 1
                    mappings.append(self._mapping_item(video))
                except Exception as exc:  # noqa: BLE001 - return per-video spike diagnostics
                    db.rollback()
                    message = f"{video.id}/{video.filename}: {exc}"
                    errors.append(message)
                    mappings.append(self._mapping_item(video, error=message))

        return CvatInitResponse(
            dataset_id=dataset.id,
            cvat_project_id=dataset.cvat_project_id,
            cvat_project_url=dataset.cvat_project_url,
            created_task_count=created_count,
            reused_task_count=reused_count,
            videos=mappings,
            error="; ".join(errors) if errors else None,
        )

    def sync_dataset(self, *, db: Session, dataset_id: str) -> CvatSyncResponse:
        dataset = self._get_video_dataset(db=db, dataset_id=dataset_id)
        videos = self._list_videos(db=db, dataset_id=dataset.id)
        health = self.health()
        mappings: list[CvatVideoMappingItem] = []
        if not health.reachable or not health.authenticated:
            status_counts = Counter(item.cvat_status or "not_initialized" for item in videos)
            return CvatSyncResponse(
                dataset_id=dataset.id,
                total_videos=len(videos),
                counts=dict(status_counts),
                issues_count=0,
                videos=[self._mapping_item(item, error=health.error) for item in videos],
                error=health.error,
            )

        with self._client(authenticated=True) as client:
            for video in videos:
                if video.cvat_task_id is None:
                    mappings.append(self._mapping_item(video))
                    continue
                self._refresh_video_mapping(client=client, db=db, video=video)
                mappings.append(self._mapping_item(video, summary=self._summarize_video(client, video)))

        counts = Counter(item.status or "not_initialized" for item in mappings)
        return CvatSyncResponse(
            dataset_id=dataset.id,
            total_videos=len(videos),
            counts=dict(counts),
            issues_count=sum(item.issue_count for item in mappings),
            videos=mappings,
            error=None,
        )

    def get_annotations_summary(self, *, db: Session, video_id: str) -> CvatAnnotationSummaryResponse:
        video = db.get(VideoItem, video_id)
        if video is None or video.dataset.data_type != DataType.VIDEO.value:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        if video.cvat_task_id is None:
            return CvatAnnotationSummaryResponse(
                video_id=video.id,
                frame_count=video.frame_count,
                review_status=video.cvat_status,
                error="CVAT task is not initialized for this video.",
            )
        with self._client(authenticated=True) as client:
            summary = self._summarize_video(client, video)
        return CvatAnnotationSummaryResponse(
            video_id=video.id,
            frame_count=video.frame_count,
            keyframe_tag_count=summary["keyframe_tag_count"],
            positive_frame_count=summary["positive_frame_count"],
            negative_frame_count=summary["negative_frame_count"],
            uncertain_frame_count=summary["uncertain_frame_count"],
            polygon_count=summary["polygon_count"],
            issue_count=summary["issue_count"],
            review_status=video.cvat_status,
        )

    def export_bline_test(self, *, dataset_id: str) -> VideoKeyframeExportResponse:
        from app.db.session import SessionLocal

        export_id = uuid4().hex
        export_root = self.settings.ensure_data_root() / "exports" / "cvat_bline" / export_id
        bundle_root = export_root / "cvat_bline_export"
        images_dir = bundle_root / "images"
        masks_dir = bundle_root / "masks"
        images_dir.mkdir(parents=True, exist_ok=True)
        masks_dir.mkdir(parents=True, exist_ok=True)

        records: list[CvatExportRecord] = []
        skipped: list[dict[str, Any]] = []

        db = SessionLocal()
        try:
            dataset = self._get_video_dataset(db=db, dataset_id=dataset_id)
            videos = self._list_videos(db=db, dataset_id=dataset.id)
            with self._client(authenticated=True) as client:
                for video in videos:
                    if video.cvat_task_id is None:
                        skipped.append(self._skip(video, None, "cvat_task_not_initialized"))
                        continue
                    parsed = self._parse_video_annotations(client, video)
                    issue_count = self._count_issues(client, video.cvat_job_id)
                    for frame_index, item in sorted(parsed.items()):
                        decision = item.get("decision")
                        reason = item.get("reason") or "manual"
                        polygons = item.get("polygons", [])
                        if decision == "uncertain":
                            skipped.append(self._skip(video, frame_index, "annotation_result_uncertain"))
                            continue
                        if decision == "positive" and not polygons:
                            skipped.append(self._skip(video, frame_index, "positive_missing_polygon"))
                            continue
                        if decision not in {"positive", "negative"}:
                            skipped.append(self._skip(video, frame_index, "missing_frame_decision"))
                            continue

                        frame = self._read_video_frame(video, frame_index)
                        image_name = f"{video.id}_{frame_index}.png"
                        mask_name = f"{video.id}_{frame_index}_mask.png"
                        image_rel = f"cvat_bline_export/images/{image_name}"
                        mask_rel = f"cvat_bline_export/masks/{mask_name}"
                        Image.fromarray(frame).save(images_dir / image_name, format="PNG")
                        if decision == "positive":
                            mask = Image.new("L", (video.width or frame.shape[1], video.height or frame.shape[0]), 0)
                            draw = ImageDraw.Draw(mask)
                            for polygon in polygons:
                                points = list(zip(polygon[0::2], polygon[1::2]))
                                draw.polygon(points, fill=1)
                            mask_type = "positive_polygon"
                        else:
                            mask = Image.new("L", (video.width or frame.shape[1], video.height or frame.shape[0]), 0)
                            mask_type = "negative_empty"
                        mask.save(masks_dir / mask_name, format="PNG")
                        records.append(
                            CvatExportRecord(
                                dataset_id=dataset.id,
                                video_id=video.id,
                                cvat_project_id=dataset.cvat_project_id,
                                cvat_task_id=video.cvat_task_id,
                                cvat_job_id=video.cvat_job_id,
                                patient_uid=video.patient.patient_uid if video.patient is not None else None,
                                lung_zone=video.lung_zone,
                                filename=video.filename,
                                frame_index=frame_index,
                                timestamp_ms=self._timestamp_ms(video, frame_index),
                                selection_reason=reason,
                                annotation_result=decision,
                                image_path=image_rel,
                                mask_path=mask_rel,
                                mask_type=mask_type,
                                review_status=video.cvat_status,
                                issue_count=issue_count,
                            )
                        )

            if not records:
                shutil.rmtree(export_root, ignore_errors=True)
                raise HTTPException(
                    status_code=400,
                    detail="No exportable CVAT B-line keyframes were found. Mark frames with Keyframe and FrameDecision first.",
                )

            self._write_export_files(bundle_root=bundle_root, records=records, skipped=skipped)
            zip_path = export_root / f"{export_id}.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in bundle_root.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_root).as_posix())

            api_base = self.settings.media_base_url.rsplit("/media", 1)[0]
            return VideoKeyframeExportResponse(
                export_id=export_id,
                dataset_id=dataset_id,
                total_labeled_count=len(records),
                skipped_count=len(skipped),
                file_path=str(zip_path),
                download_url=f"{api_base}/api/video-exports/{export_id}/download",
            )
        finally:
            db.close()

    def _client(self, *, authenticated: bool) -> httpx.Client:
        headers = {"Accept": "application/vnd.cvat+json"}
        if authenticated:
            token = self.settings.cvat_access_token or self._login_for_token()
            headers["Authorization"] = f"Token {token}"
        return httpx.Client(base_url=self.base_url, timeout=60.0, headers=headers, trust_env=False)

    def _login_for_token(self) -> str:
        if not self.settings.cvat_username or not self.settings.cvat_password:
            raise HTTPException(status_code=503, detail="CVAT_USERNAME/CVAT_PASSWORD are not configured.")
        with httpx.Client(base_url=self.base_url, timeout=30.0, trust_env=False) as client:
            response = client.post(
                "/api/auth/login",
                json={"username": self.settings.cvat_username, "password": self.settings.cvat_password},
            )
            response.raise_for_status()
        token = response.json().get("key")
        if not token:
            raise HTTPException(status_code=503, detail="CVAT login did not return an access token.")
        return str(token)

    def _create_project(self, client: httpx.Client, dataset: Dataset) -> dict[str, Any]:
        payload = {
            "name": f"{dataset.name} ({dataset.id})",
            "labels": self._label_config(),
        }
        response = client.post("/api/projects", json=payload)
        response.raise_for_status()
        return response.json()

    def _create_task(self, *, client: httpx.Client, dataset: Dataset, video: VideoItem) -> dict[str, Any]:
        payload = {
            "name": f"{video.filename} ({video.id})",
            "project_id": dataset.cvat_project_id,
            "segment_size": max(video.frame_count or 1, 1),
            "overlap": 0,
            "consensus_replicas": 0,
        }
        response = client.post("/api/tasks", json=payload)
        response.raise_for_status()
        return response.json()

    def _upload_video_to_task(self, *, client: httpx.Client, video: VideoItem) -> None:
        video_path = Path(video.file_path)
        if not video_path.exists():
            raise HTTPException(status_code=400, detail=f"Video file does not exist: {video.filename}")
        with video_path.open("rb") as file_obj:
            files = {"client_files[0]": (video.filename, file_obj, "video/mp4")}
            data = {"image_quality": "75", "use_zip_chunks": "false"}
            response = client.post(f"/api/tasks/{video.cvat_task_id}/data", data=data, files=files, timeout=300.0)
        response.raise_for_status()
        rq_id = response.json().get("rq_id")
        if rq_id:
            self._wait_request(client, str(rq_id))

    def _wait_request(self, client: httpx.Client, rq_id: str) -> None:
        deadline = time.time() + REQUEST_TIMEOUT_SECONDS
        last_payload: dict[str, Any] = {}
        while time.time() < deadline:
            response = client.get(f"/api/requests/{rq_id}")
            response.raise_for_status()
            last_payload = response.json()
            status = str(last_payload.get("status", "")).lower()
            if status in {"finished", "completed"}:
                return
            if status in {"failed", "error"}:
                raise HTTPException(status_code=502, detail=f"CVAT request {rq_id} failed: {last_payload}")
            time.sleep(2)
        raise HTTPException(status_code=504, detail=f"Timed out waiting for CVAT request {rq_id}: {last_payload}")

    def _refresh_video_mapping(self, *, client: httpx.Client, db: Session, video: VideoItem) -> None:
        if video.cvat_task_id is None:
            return
        task = client.get(f"/api/tasks/{video.cvat_task_id}")
        task.raise_for_status()
        task_payload = task.json()
        video.cvat_status = self._map_task_status(task_payload)
        video.cvat_task_url = self._build_task_url(video.cvat_task_id)

        jobs = client.get("/api/jobs", params={"task_id": video.cvat_task_id, "page_size": 10})
        jobs.raise_for_status()
        job_items = self._collection_results(jobs.json())
        if job_items:
            job = job_items[0]
            video.cvat_job_id = int(job["id"])
            video.cvat_job_url = self._build_job_url(video.cvat_job_id)
            video.cvat_status = str(job.get("state") or job.get("stage") or video.cvat_status or "created")
        video.cvat_annotation_updated_at = datetime.now(timezone.utc)
        db.add(video)
        db.commit()
        db.refresh(video)

    def _summarize_video(self, client: httpx.Client, video: VideoItem) -> dict[str, int]:
        if video.cvat_task_id is None:
            return self._empty_summary()
        annotations = client.get(f"/api/tasks/{video.cvat_task_id}/annotations")
        annotations.raise_for_status()
        payload = annotations.json()
        labels = self._labels_by_name(client, video.cvat_task_id)
        keyframe_label_ids = {label_id for name, label_id in labels.items() if name.startswith("Keyframe")}
        decision_label_ids = {
            "positive": labels.get("FrameDecision:positive") or labels.get("positive"),
            "negative": labels.get("FrameDecision:negative") or labels.get("negative"),
            "uncertain": labels.get("FrameDecision:uncertain") or labels.get("uncertain"),
        }
        polygon_label_id = labels.get("B-line")
        tags = payload.get("tags") or []
        shapes = payload.get("shapes") or []
        issues_count = self._count_issues(client, video.cvat_job_id)
        return {
            "keyframe_tag_count": sum(1 for item in tags if item.get("label_id") in keyframe_label_ids),
            "positive_frame_count": sum(1 for item in tags if item.get("label_id") == decision_label_ids["positive"]),
            "negative_frame_count": sum(1 for item in tags if item.get("label_id") == decision_label_ids["negative"]),
            "uncertain_frame_count": sum(1 for item in tags if item.get("label_id") == decision_label_ids["uncertain"]),
            "polygon_count": sum(1 for item in shapes if item.get("label_id") == polygon_label_id and item.get("type") == "polygon"),
            "issue_count": issues_count,
        }

    def _parse_video_annotations(self, client: httpx.Client, video: VideoItem) -> dict[int, dict[str, Any]]:
        annotations = client.get(f"/api/tasks/{video.cvat_task_id}/annotations")
        annotations.raise_for_status()
        payload = annotations.json()
        labels = self._label_names_by_id(client, int(video.cvat_task_id))
        by_frame: dict[int, dict[str, Any]] = {}
        for tag in payload.get("tags") or []:
            frame = int(tag.get("frame", 0))
            label_name = labels.get(int(tag.get("label_id", -1)), "")
            entry = by_frame.setdefault(frame, {"polygons": []})
            if label_name.startswith("Keyframe:"):
                entry["reason"] = label_name.split(":", 1)[1]
            elif label_name.startswith("FrameDecision:"):
                entry["decision"] = label_name.split(":", 1)[1]
        for shape in payload.get("shapes") or []:
            if shape.get("type") != "polygon":
                continue
            frame = int(shape.get("frame", 0))
            label_name = labels.get(int(shape.get("label_id", -1)), "")
            if label_name != "B-line":
                continue
            by_frame.setdefault(frame, {"polygons": []})["polygons"].append(shape.get("points") or [])
        return {frame: item for frame, item in by_frame.items() if item.get("reason")}

    def _labels_by_name(self, client: httpx.Client, task_id: int) -> dict[str, int]:
        response = client.get("/api/labels", params={"task_id": task_id, "page_size": 100})
        response.raise_for_status()
        return {str(item["name"]): int(item["id"]) for item in self._collection_results(response.json())}

    def _label_names_by_id(self, client: httpx.Client, task_id: int) -> dict[int, str]:
        response = client.get("/api/labels", params={"task_id": task_id, "page_size": 100})
        response.raise_for_status()
        return {int(item["id"]): str(item["name"]) for item in self._collection_results(response.json())}

    def _count_issues(self, client: httpx.Client, job_id: int | None) -> int:
        if job_id is None:
            return 0
        response = client.get("/api/issues", params={"job_id": job_id, "page_size": 1})
        if response.status_code >= 400:
            return 0
        payload = response.json()
        if isinstance(payload, dict) and "count" in payload:
            return int(payload["count"])
        return len(self._collection_results(payload))

    def _endpoint_available(self, client: httpx.Client, path: str) -> bool:
        response = client.get(path, params={"page_size": 1})
        return response.status_code not in {404, 405}

    def _label_config(self) -> list[dict[str, Any]]:
        keyframe_reasons = [
            "first_clear",
            "most_obvious",
            "appear",
            "disappear",
            "count_change",
            "confluent_most_obvious",
            "boundary_change",
            "issue_frame",
            "manual",
        ]
        return [
            {
                "name": "B-line",
                "color": "#ff4d4f",
                "type": "polygon",
            },
            *[
                {
                    "name": f"Keyframe:{reason}",
                    "color": "#1677ff",
                    "type": "tag",
                }
                for reason in keyframe_reasons
            ],
            *[
                {
                    "name": f"FrameDecision:{decision}",
                    "color": color,
                    "type": "tag",
                }
                for decision, color in [
                    ("positive", "#52c41a"),
                    ("negative", "#8c8c8c"),
                    ("uncertain", "#faad14"),
                ]
            ],
        ]

    def _map_task_status(self, task_payload: dict[str, Any]) -> str:
        return str(task_payload.get("state") or task_payload.get("status") or task_payload.get("mode") or "created")

    def _collection_results(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            return payload["results"]
        if isinstance(payload, list):
            return payload
        return []

    def _empty_summary(self) -> dict[str, int]:
        return {
            "keyframe_tag_count": 0,
            "positive_frame_count": 0,
            "negative_frame_count": 0,
            "uncertain_frame_count": 0,
            "polygon_count": 0,
            "issue_count": 0,
        }

    def _read_video_frame(self, video: VideoItem, frame_index: int):
        import cv2  # type: ignore

        capture = cv2.VideoCapture(video.file_path)
        try:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
        finally:
            capture.release()
        if not ok or frame is None:
            raise HTTPException(status_code=400, detail=f"Could not read frame {frame_index} from {video.filename}.")
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def _timestamp_ms(self, video: VideoItem, frame_index: int) -> int:
        if not video.fps:
            return 0
        return int(round((frame_index / video.fps) * 1000))

    def _skip(self, video: VideoItem, frame_index: int | None, reason: str) -> dict[str, Any]:
        return {
            "video_id": video.id,
            "cvat_task_id": video.cvat_task_id,
            "cvat_job_id": video.cvat_job_id,
            "filename": video.filename,
            "frame_index": frame_index,
            "skip_reason": reason,
        }

    def _write_export_files(
        self,
        *,
        bundle_root: Path,
        records: list[CvatExportRecord],
        skipped: list[dict[str, Any]],
    ) -> None:
        manifest = [asdict(item) for item in records]
        (bundle_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (bundle_root / "skipped.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")
        with (bundle_root / "manifest.csv").open("w", newline="", encoding="utf-8") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=list(manifest[0].keys()))
            writer.writeheader()
            writer.writerows(manifest)
        (bundle_root / "README.txt").write_text(
            "\n".join(
                [
                    "CVAT B-line export spike",
                    "positive frames contain B-line polygon masks with pixel values 0/1.",
                    "negative frames contain empty masks with pixel value 0.",
                    "uncertain or incomplete frames are listed in skipped.json.",
                ]
            ),
            encoding="utf-8",
        )

    def _mapping_item(
        self,
        video: VideoItem,
        *,
        error: str | None = None,
        summary: dict[str, int] | None = None,
    ) -> CvatVideoMappingItem:
        counts = summary or self._empty_summary()
        return CvatVideoMappingItem(
            video_id=video.id,
            cvat_task_id=video.cvat_task_id,
            cvat_job_id=video.cvat_job_id,
            cvat_task_url=video.cvat_task_url,
            cvat_job_url=video.cvat_job_url,
            status=video.cvat_status or "not_initialized",
            keyframe_tag_count=counts["keyframe_tag_count"],
            positive_frame_count=counts["positive_frame_count"],
            negative_frame_count=counts["negative_frame_count"],
            uncertain_frame_count=counts["uncertain_frame_count"],
            polygon_count=counts["polygon_count"],
            issue_count=counts["issue_count"],
            error=error,
        )

    def _headers(self) -> dict[str, str]:
        if self.settings.cvat_access_token:
            return {"Authorization": f"Token {self.settings.cvat_access_token}"}
        return {}

    def _get_video_dataset(self, *, db: Session, dataset_id: str) -> Dataset:
        dataset = db.get(Dataset, dataset_id)
        if dataset is None or dataset.data_type != DataType.VIDEO.value:
            raise HTTPException(status_code=404, detail=f"Video dataset not found: {dataset_id}")
        return dataset

    def _list_videos(self, *, db: Session, dataset_id: str) -> list[VideoItem]:
        return (
            db.query(VideoItem)
            .filter(VideoItem.dataset_id == dataset_id)
            .order_by(VideoItem.created_at.asc())
            .all()
        )

    def _build_project_url(self, project_id: int) -> str:
        return f"{self.base_url}/projects/{project_id}"

    def _build_task_url(self, task_id: int) -> str:
        return f"{self.base_url}/tasks/{task_id}"

    def _build_job_url(self, job_id: int) -> str:
        return f"{self.base_url}/tasks/jobs/{job_id}"
