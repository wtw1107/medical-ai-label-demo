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
    CvatAccessResponse,
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
    unresolved_issue_count: int
    resolved_issue_count: int
    cvat_task_status: str | None
    cvat_job_state: str | None
    cvat_job_stage: str | None
    exported_at: str


@dataclass
class ParsedCvatFrame:
    frame_index: int
    selection_reasons: list[str]
    annotation_results: list[str]
    polygons: list[list[float]]
    issues: list[dict[str, Any]]
    issue_count: int
    unresolved_issue_count: int
    resolved_issue_count: int
    conflicts: list[str]

    @property
    def selection_reason(self) -> str | None:
        return self.selection_reasons[0] if self.selection_reasons else None

    @property
    def annotation_result(self) -> str | None:
        return self.annotation_results[0] if self.annotation_results else None


@dataclass
class CvatAccessContext:
    owner_user_id: int | None
    owner_username: str | None
    assignee_user_id: int | None
    assignee_username: str | None
    organization_slug: str | None
    warning: str | None = None


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
                current_user = self._get_current_user(client)
                assignee_username = self._target_assignee_username(current_user)
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
            authenticated_username=str(current_user.get("username")) if current_user.get("username") else None,
            default_assignee_username=assignee_username,
            organization_slug=self._organization_slug(),
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
                repaired_task_count=0,
                failed_task_count=0,
                videos=[self._mapping_item(item, error=health.error) for item in videos],
                error=health.error or "CVAT is not reachable or authenticated.",
            )

        created_count = 0
        reused_count = 0
        repaired_count = 0
        failed_count = 0
        errors: list[str] = []
        mappings: list[CvatVideoMappingItem] = []

        with self._client(authenticated=True) as client:
            access_context = self._resolve_access_context(client)
            if dataset.cvat_project_id is not None and not self._project_exists(client, dataset.cvat_project_id):
                self._clear_dataset_cvat_mapping(db=db, dataset=dataset, videos=videos)

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
                    mapping_check = self._video_remote_mapping_status(client=client, dataset=dataset, video=video)
                    if mapping_check["valid"]:
                        reused_count += 1
                        self._refresh_video_mapping(client=client, db=db, video=video, access_context=access_context)
                        mappings.append(self._mapping_item(video))
                        continue
                    self._clear_video_cvat_mapping(db=db, video=video)
                    repaired_count += 1

                try:
                    task = self._create_task(client=client, dataset=dataset, video=video, access_context=access_context)
                    video.cvat_task_id = int(task["id"])
                    video.cvat_task_url = self._build_task_url(video.cvat_task_id)
                    video.cvat_status = "uploading"
                    db.add(video)
                    db.commit()
                    db.refresh(video)

                    self._upload_video_to_task(client=client, video=video)
                    self._refresh_video_mapping(client=client, db=db, video=video, access_context=access_context)
                    created_count += 1
                    mappings.append(self._mapping_item(video))
                except Exception as exc:  # noqa: BLE001 - return per-video spike diagnostics
                    db.rollback()
                    failed_count += 1
                    message = f"{video.id}/{video.filename}: {exc}"
                    errors.append(message)
                    mappings.append(self._mapping_item(video, error=message))

        return CvatInitResponse(
            dataset_id=dataset.id,
            cvat_project_id=dataset.cvat_project_id,
            cvat_project_url=dataset.cvat_project_url,
            created_task_count=created_count,
            reused_task_count=reused_count,
            repaired_task_count=repaired_count,
            failed_task_count=failed_count,
            videos=mappings,
            owner_username=access_context.owner_username,
            assignee_username=access_context.assignee_username,
            organization_slug=access_context.organization_slug,
            warning=access_context.warning,
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
            access_context = self._resolve_access_context(client)
            for video in videos:
                if video.cvat_task_id is None:
                    mappings.append(self._mapping_item(video))
                    continue
                mapping_check = self._video_remote_mapping_status(client=client, dataset=dataset, video=video)
                if not mapping_check["valid"]:
                    video.cvat_status = "invalid_remote_mapping"
                    db.add(video)
                    db.commit()
                    db.refresh(video)
                    mappings.append(self._mapping_item(video, error=mapping_check["warning"] or "CVAT 标注任务已失效，请重新初始化。"))
                    continue
                self._refresh_video_mapping(client=client, db=db, video=video, access_context=access_context)
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

    def get_video_access(self, *, db: Session, video_id: str) -> CvatAccessResponse:
        video = db.get(VideoItem, video_id)
        if video is None or video.dataset.data_type != DataType.VIDEO.value:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

        if video.cvat_task_id is None or video.cvat_job_id is None:
            return CvatAccessResponse(
                video_id=video.id,
                initialized=False,
                task_exists=video.cvat_task_id is not None,
                job_exists=False,
                organization_slug=self._organization_slug(),
                job_url=video.cvat_job_url,
                access_ready=False,
                warning="CVAT task/job is not initialized for this video. Create CVAT tasks first.",
            )

        try:
            with self._client(authenticated=True) as client:
                access_context = self._resolve_access_context(client)
                task_payload = self._get_task_payload(client, video.cvat_task_id)
                job_payload = self._get_job_payload(client, video.cvat_job_id)
                project_exists = self._project_exists(client, video.dataset.cvat_project_id) if video.dataset.cvat_project_id is not None else False
        except httpx.HTTPStatusError as exc:
            return CvatAccessResponse(
                video_id=video.id,
                initialized=True,
                task_exists=False,
                job_exists=False,
                organization_slug=self._organization_slug(),
                job_url=video.cvat_job_url,
                access_ready=False,
                warning=f"CVAT access check failed with HTTP {exc.response.status_code}.",
            )
        except httpx.HTTPError as exc:
            return CvatAccessResponse(
                video_id=video.id,
                initialized=True,
                task_exists=False,
                job_exists=False,
                organization_slug=self._organization_slug(),
                job_url=video.cvat_job_url,
                access_ready=False,
                warning=f"Could not reach CVAT for access check: {exc}",
            )

        task_exists = task_payload is not None
        job_exists = job_payload is not None
        owner_username = self._username_from_user_ref(task_payload.get("owner") if task_payload else None)
        assignee_username = self._username_from_user_ref(task_payload.get("assignee") if task_payload else None)
        job_task_id = self._job_task_id(job_payload) if job_payload else None
        expected_url = self._build_job_url(video.cvat_job_id, task_id=video.cvat_task_id)
        warning_parts: list[str] = []
        if access_context.warning:
            warning_parts.append(access_context.warning)
        if video.dataset.cvat_project_id is not None and not project_exists:
            warning_parts.append("平台保存的 CVAT Project 已不存在，请重新初始化标注任务。")
        if not task_exists:
            warning_parts.append("平台保存的 CVAT Task 已不存在，请重新初始化标注任务。")
        if not job_exists:
            warning_parts.append("平台保存的 CVAT Job 已不存在，请重新初始化标注任务。")
        if job_exists and job_task_id is not None and job_task_id != video.cvat_task_id:
            warning_parts.append("平台保存的 CVAT Job 不属于当前 Task，请重新初始化标注任务。")
        if task_exists and not assignee_username:
            warning_parts.append("CVAT task has no assignee; the owner can still open it, but other accounts may not see it.")
        elif task_exists and access_context.assignee_username and assignee_username != access_context.assignee_username:
            warning_parts.append(f"CVAT task is assigned to {assignee_username}, not configured assignee {access_context.assignee_username}.")

        return CvatAccessResponse(
            video_id=video.id,
            initialized=True,
            task_exists=task_exists,
            job_exists=job_exists,
            owner_username=owner_username or access_context.owner_username,
            assignee_username=assignee_username or access_context.assignee_username,
            organization_slug=access_context.organization_slug,
            job_url=expected_url if task_exists and job_exists and (job_task_id in {None, video.cvat_task_id}) else None,
            access_ready=task_exists and job_exists and project_exists and (job_task_id in {None, video.cvat_task_id}),
            warning=" ".join(warning_parts) if warning_parts else None,
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
            mapping_check = self._video_remote_mapping_status(client=client, dataset=video.dataset, video=video)
            if not mapping_check["valid"]:
                return CvatAnnotationSummaryResponse(
                    video_id=video.id,
                    frame_count=video.frame_count,
                    review_status="invalid_remote_mapping",
                    error=mapping_check["warning"] or "CVAT 标注任务已失效，请重新初始化。",
                )
            summary = self._summarize_video(client, video)
        return CvatAnnotationSummaryResponse(
            video_id=video.id,
            frame_count=video.frame_count,
            selected_keyframe_count=summary["selected_keyframe_count"],
            pending_frame_count=summary["pending_frame_count"],
            keyframe_tag_count=summary["keyframe_tag_count"],
            positive_frame_count=summary["positive_frame_count"],
            negative_frame_count=summary["negative_frame_count"],
            uncertain_frame_count=summary["uncertain_frame_count"],
            polygon_count=summary["polygon_count"],
            issue_count=summary["issue_count"],
            unresolved_issue_count=summary["unresolved_issue_count"],
            resolved_issue_count=summary["resolved_issue_count"],
            cvat_task_status=summary.get("cvat_task_status"),
            cvat_job_state=summary.get("cvat_job_state"),
            cvat_job_stage=summary.get("cvat_job_stage"),
            annotation_updated_at=video.cvat_annotation_updated_at,
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
        exported_at = datetime.now(timezone.utc).isoformat()

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
                    video_issues = self._list_issues(client, video.cvat_job_id)
                    unscoped_unresolved_issues = [
                        issue for issue in video_issues if self._issue_frame(issue) is None and not self._issue_resolved(issue)
                    ]
                    task_payload = self._get_task_payload(client, video.cvat_task_id)
                    job_payload = self._get_job_payload(client, video.cvat_job_id)
                    for frame_index, item in sorted(parsed.items()):
                        decision = item.annotation_result
                        reason = item.selection_reason or "manual"
                        polygons = item.polygons
                        if item.conflicts:
                            skipped.append(self._skip(video, frame_index, ",".join(item.conflicts)))
                            continue
                        if item.unresolved_issue_count > 0 or unscoped_unresolved_issues:
                            skipped.append(self._skip(video, frame_index, "unresolved_issue"))
                            continue
                        if decision == "uncertain":
                            skipped.append(self._skip(video, frame_index, "annotation_result_uncertain"))
                            continue
                        if decision == "positive" and not polygons:
                            skipped.append(self._skip(video, frame_index, "positive_missing_polygon"))
                            continue
                        if decision == "negative" and polygons:
                            skipped.append(self._skip(video, frame_index, "negative_has_polygon_conflict"))
                            continue
                        if decision not in {"positive", "negative"}:
                            skipped.append(self._skip(video, frame_index, "annotation_result_pending"))
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
                                review_status=self._review_status(item.issue_count, item.unresolved_issue_count),
                                issue_count=item.issue_count,
                                unresolved_issue_count=item.unresolved_issue_count,
                                resolved_issue_count=item.resolved_issue_count,
                                cvat_task_status=self._map_task_status(task_payload) if task_payload else video.cvat_status,
                                cvat_job_state=str(job_payload.get("state")) if job_payload and job_payload.get("state") is not None else None,
                                cvat_job_stage=str(job_payload.get("stage")) if job_payload and job_payload.get("stage") is not None else None,
                                exported_at=exported_at,
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
        organization_slug = self._organization_slug()
        if organization_slug:
            headers["X-Organization"] = organization_slug
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

    def _organization_slug(self) -> str | None:
        value = (self.settings.cvat_organization or "").strip()
        return value or None

    def _get_current_user(self, client: httpx.Client) -> dict[str, Any]:
        response = client.get("/api/users/self")
        response.raise_for_status()
        return response.json()

    def _target_assignee_username(self, current_user: dict[str, Any]) -> str | None:
        configured = (self.settings.cvat_default_assignee_username or "").strip()
        if configured:
            return configured
        username = (self.settings.cvat_username or "").strip()
        if username:
            return username
        current_username = current_user.get("username")
        return str(current_username) if current_username else None

    def _resolve_access_context(self, client: httpx.Client) -> CvatAccessContext:
        current_user = self._get_current_user(client)
        owner_user_id = self._safe_int(current_user.get("id"))
        owner_username = str(current_user.get("username")) if current_user.get("username") else None
        target_username = self._target_assignee_username(current_user)
        assignee = self._find_user_by_username(client, target_username) if target_username else None
        warning = None
        if target_username and assignee is None:
            warning = f"Configured CVAT assignee '{target_username}' was not found; tasks will stay owned by {owner_username or 'the authenticated user'}."
        return CvatAccessContext(
            owner_user_id=owner_user_id,
            owner_username=owner_username,
            assignee_user_id=self._safe_int(assignee.get("id")) if assignee else owner_user_id,
            assignee_username=str(assignee.get("username")) if assignee and assignee.get("username") else owner_username,
            organization_slug=self._organization_slug(),
            warning=warning,
        )

    def _find_user_by_username(self, client: httpx.Client, username: str | None) -> dict[str, Any] | None:
        if not username:
            return None
        response = client.get("/api/users", params={"search": username, "page_size": 100})
        response.raise_for_status()
        for item in self._collection_results(response.json()):
            if str(item.get("username") or "").lower() == username.lower():
                return item
        return None

    def _assign_task_if_needed(self, *, client: httpx.Client, task_id: int, access_context: CvatAccessContext) -> None:
        if access_context.assignee_user_id is None:
            return
        current = client.get(f"/api/tasks/{task_id}")
        current.raise_for_status()
        current_assignee = current.json().get("assignee")
        current_assignee_id = self._safe_int(current_assignee.get("id")) if isinstance(current_assignee, dict) else None
        if current_assignee_id == access_context.assignee_user_id:
            return
        response = client.patch(f"/api/tasks/{task_id}", json={"assignee_id": access_context.assignee_user_id})
        response.raise_for_status()

    def _username_from_user_ref(self, value: Any) -> str | None:
        if isinstance(value, dict) and value.get("username"):
            return str(value["username"])
        return None

    def _job_task_id(self, job_payload: dict[str, Any]) -> int | None:
        task_id = self._safe_int(job_payload.get("task_id"))
        if task_id is not None:
            return task_id
        task_value = job_payload.get("task")
        if isinstance(task_value, dict):
            return self._safe_int(task_value.get("id"))
        return self._safe_int(task_value)

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _create_project(self, client: httpx.Client, dataset: Dataset) -> dict[str, Any]:
        payload = {
            "name": f"{dataset.name} ({dataset.id})",
            "labels": self._label_config(),
        }
        response = client.post("/api/projects", json=payload)
        response.raise_for_status()
        return response.json()

    def _create_task(
        self,
        *,
        client: httpx.Client,
        dataset: Dataset,
        video: VideoItem,
        access_context: CvatAccessContext,
    ) -> dict[str, Any]:
        payload = {
            "name": f"{video.filename} ({video.id})",
            "project_id": dataset.cvat_project_id,
            "segment_size": max(video.frame_count or 1, 1),
            "overlap": 0,
            "consensus_replicas": 0,
        }
        if access_context.assignee_user_id is not None:
            payload["assignee_id"] = access_context.assignee_user_id
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

    def _refresh_video_mapping(
        self,
        *,
        client: httpx.Client,
        db: Session,
        video: VideoItem,
        access_context: CvatAccessContext | None = None,
    ) -> None:
        if video.cvat_task_id is None:
            return
        if access_context and access_context.assignee_user_id is not None:
            self._assign_task_if_needed(client=client, task_id=video.cvat_task_id, access_context=access_context)
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
            video.cvat_job_url = self._build_job_url(video.cvat_job_id, task_id=video.cvat_task_id)
            video.cvat_status = str(job.get("state") or job.get("stage") or video.cvat_status or "created")
        video.cvat_annotation_updated_at = datetime.now(timezone.utc)
        db.add(video)
        db.commit()
        db.refresh(video)

    def _summarize_video(self, client: httpx.Client, video: VideoItem) -> dict[str, Any]:
        if video.cvat_task_id is None:
            return self._empty_summary()
        parsed = self._parse_video_annotations(client, video)
        task_payload = self._get_task_payload(client, video.cvat_task_id)
        job_payload = self._get_job_payload(client, video.cvat_job_id)
        all_issues = self._list_issues(client, video.cvat_job_id)
        issue_count = len(all_issues)
        unresolved_issue_count = sum(1 for issue in all_issues if not self._issue_resolved(issue))
        resolved_issue_count = issue_count - unresolved_issue_count
        return {
            "selected_keyframe_count": len(parsed),
            "pending_frame_count": sum(1 for item in parsed.values() if not item.annotation_result),
            "keyframe_tag_count": sum(len(item.selection_reasons) for item in parsed.values()),
            "positive_frame_count": sum(1 for item in parsed.values() if item.annotation_result == "positive"),
            "negative_frame_count": sum(1 for item in parsed.values() if item.annotation_result == "negative"),
            "uncertain_frame_count": sum(1 for item in parsed.values() if item.annotation_result == "uncertain"),
            "polygon_count": sum(len(item.polygons) for item in parsed.values()),
            "issue_count": issue_count,
            "unresolved_issue_count": unresolved_issue_count,
            "resolved_issue_count": resolved_issue_count,
            "cvat_task_status": self._map_task_status(task_payload) if task_payload else video.cvat_status,
            "cvat_job_state": str(job_payload.get("state")) if job_payload and job_payload.get("state") is not None else None,
            "cvat_job_stage": str(job_payload.get("stage")) if job_payload and job_payload.get("stage") is not None else None,
        }

    def _parse_video_annotations(self, client: httpx.Client, video: VideoItem) -> dict[int, ParsedCvatFrame]:
        annotations = client.get(f"/api/tasks/{video.cvat_task_id}/annotations")
        annotations.raise_for_status()
        payload = annotations.json()
        labels = self._label_names_by_id(client, int(video.cvat_task_id))
        by_frame: dict[int, dict[str, Any]] = {}
        for tag in payload.get("tags") or []:
            frame = int(tag.get("frame", 0))
            label_name = labels.get(int(tag.get("label_id", -1)), "")
            entry = by_frame.setdefault(frame, {"reasons": [], "decisions": [], "polygons": [], "conflicts": []})
            if label_name.startswith("Keyframe:"):
                entry["reasons"].append(label_name.split(":", 1)[1])
            elif label_name.startswith("FrameDecision:"):
                entry["decisions"].append(label_name.split(":", 1)[1])
        for shape in payload.get("shapes") or []:
            if shape.get("type") != "polygon":
                continue
            frame = int(shape.get("frame", 0))
            label_name = labels.get(int(shape.get("label_id", -1)), "")
            if label_name != "B-line":
                continue
            entry = by_frame.setdefault(frame, {"reasons": [], "decisions": [], "polygons": [], "conflicts": []})
            entry["polygons"].append([float(point) for point in (shape.get("points") or [])])

        issues_by_frame: dict[int, list[dict[str, Any]]] = {}
        for issue in self._list_issues(client, video.cvat_job_id):
            frame = self._issue_frame(issue)
            if frame is not None:
                issues_by_frame.setdefault(frame, []).append(issue)

        parsed: dict[int, ParsedCvatFrame] = {}
        for frame, item in by_frame.items():
            reasons = list(dict.fromkeys(item.get("reasons") or []))
            decisions = list(dict.fromkeys(item.get("decisions") or []))
            if not reasons:
                continue
            conflicts = list(item.get("conflicts") or [])
            if len(reasons) > 1:
                conflicts.append("duplicate_selection_reason")
            if len(decisions) > 1:
                conflicts.append("conflicting_frame_decision")
            frame_issues = issues_by_frame.get(frame, [])
            unresolved = [issue for issue in frame_issues if not self._issue_resolved(issue)]
            resolved = [issue for issue in frame_issues if self._issue_resolved(issue)]
            parsed[frame] = ParsedCvatFrame(
                frame_index=frame,
                selection_reasons=reasons,
                annotation_results=decisions,
                polygons=item.get("polygons") or [],
                issues=frame_issues,
                issue_count=len(frame_issues),
                unresolved_issue_count=len(unresolved),
                resolved_issue_count=len(resolved),
                conflicts=conflicts,
            )
        return parsed

    def _labels_by_name(self, client: httpx.Client, task_id: int) -> dict[str, int]:
        response = client.get("/api/labels", params={"task_id": task_id, "page_size": 100})
        response.raise_for_status()
        return {str(item["name"]): int(item["id"]) for item in self._collection_results(response.json())}

    def _label_names_by_id(self, client: httpx.Client, task_id: int) -> dict[int, str]:
        response = client.get("/api/labels", params={"task_id": task_id, "page_size": 100})
        response.raise_for_status()
        return {int(item["id"]): str(item["name"]) for item in self._collection_results(response.json())}

    def _get_task_payload(self, client: httpx.Client, task_id: int | None) -> dict[str, Any] | None:
        if task_id is None:
            return None
        response = client.get(f"/api/tasks/{task_id}")
        if response.status_code >= 400:
            return None
        return response.json()

    def _get_job_payload(self, client: httpx.Client, job_id: int | None) -> dict[str, Any] | None:
        if job_id is None:
            return None
        response = client.get(f"/api/jobs/{job_id}")
        if response.status_code >= 400:
            return None
        return response.json()

    def _project_exists(self, client: httpx.Client, project_id: int | None) -> bool:
        if project_id is None:
            return False
        response = client.get(f"/api/projects/{project_id}")
        return response.status_code < 400

    def _video_remote_mapping_status(self, *, client: httpx.Client, dataset: Dataset, video: VideoItem) -> dict[str, Any]:
        project_exists = self._project_exists(client, dataset.cvat_project_id)
        task_payload = self._get_task_payload(client, video.cvat_task_id)
        job_payload = self._get_job_payload(client, video.cvat_job_id)
        job_task_id = self._job_task_id(job_payload) if job_payload else None
        warning_parts: list[str] = []
        if dataset.cvat_project_id is not None and not project_exists:
            warning_parts.append("平台保存的 CVAT Project 已不存在，请重新初始化标注任务。")
        if video.cvat_task_id is not None and task_payload is None:
            warning_parts.append("平台保存的 CVAT Task 已不存在，请重新初始化标注任务。")
        if video.cvat_job_id is not None and job_payload is None:
            warning_parts.append("平台保存的 CVAT Job 已不存在，请重新初始化标注任务。")
        if job_task_id is not None and video.cvat_task_id is not None and job_task_id != video.cvat_task_id:
            warning_parts.append("平台保存的 CVAT Job 不属于当前 Task，请重新初始化标注任务。")
        valid = bool(
            (dataset.cvat_project_id is None or project_exists)
            and (video.cvat_task_id is None or task_payload is not None)
            and (video.cvat_job_id is None or (job_payload is not None and job_task_id in {None, video.cvat_task_id}))
        )
        return {
            "valid": valid,
            "project_exists": project_exists,
            "task_payload": task_payload,
            "job_payload": job_payload,
            "warning": " ".join(warning_parts) if warning_parts else None,
        }

    def _clear_dataset_cvat_mapping(self, *, db: Session, dataset: Dataset, videos: list[VideoItem]) -> None:
        dataset.cvat_project_id = None
        dataset.cvat_project_url = None
        db.add(dataset)
        for video in videos:
            self._clear_video_cvat_mapping(db=db, video=video, commit=False)
        db.commit()
        db.refresh(dataset)
        for video in videos:
            db.refresh(video)

    def _clear_video_cvat_mapping(self, *, db: Session, video: VideoItem, commit: bool = True) -> None:
        video.cvat_task_id = None
        video.cvat_job_id = None
        video.cvat_task_url = None
        video.cvat_job_url = None
        video.cvat_status = "invalid_remote_mapping"
        video.cvat_annotation_updated_at = datetime.now(timezone.utc)
        db.add(video)
        if commit:
            db.commit()
            db.refresh(video)

    def _list_issues(self, client: httpx.Client, job_id: int | None) -> list[dict[str, Any]]:
        if job_id is None:
            return []
        items: list[dict[str, Any]] = []
        url = "/api/issues"
        params: dict[str, Any] | None = {"job_id": job_id, "page_size": 100}
        while url:
            response = client.get(url, params=params)
            if response.status_code >= 400:
                return []
            payload = response.json()
            page_items = self._collection_results(payload)
            items.extend(page_items)
            next_url = payload.get("next") if isinstance(payload, dict) else None
            if not next_url:
                break
            url = str(next_url).replace(self.base_url, "")
            params = None
        return items

    def _issue_resolved(self, issue: dict[str, Any]) -> bool:
        if isinstance(issue.get("resolved"), bool):
            return bool(issue["resolved"])
        status = str(issue.get("status") or issue.get("state") or "").lower()
        if status in {"resolved", "closed", "done"}:
            return True
        if issue.get("resolved_date") or issue.get("resolved_at"):
            return True
        return False

    def _issue_frame(self, issue: dict[str, Any]) -> int | None:
        for key in ("frame", "object_frame"):
            value = issue.get(key)
            if value is not None:
                return int(value)
        position = issue.get("position")
        if isinstance(position, dict):
            for key in ("frame", "frame_id"):
                value = position.get(key)
                if value is not None:
                    return int(value)
        return None

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

    def _empty_summary(self) -> dict[str, Any]:
        return {
            "selected_keyframe_count": 0,
            "pending_frame_count": 0,
            "keyframe_tag_count": 0,
            "positive_frame_count": 0,
            "negative_frame_count": 0,
            "uncertain_frame_count": 0,
            "polygon_count": 0,
            "issue_count": 0,
            "unresolved_issue_count": 0,
            "resolved_issue_count": 0,
            "cvat_task_status": None,
            "cvat_job_state": None,
            "cvat_job_stage": None,
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

    def _review_status(self, issue_count: int, unresolved_issue_count: int) -> str:
        if unresolved_issue_count > 0:
            return "changes_requested"
        if issue_count > 0:
            return "issue_resolved"
        return "not_reviewed"

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
            unresolved_issue_count=counts["unresolved_issue_count"],
            resolved_issue_count=counts["resolved_issue_count"],
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

    def _build_job_url(self, job_id: int, *, task_id: int | None = None) -> str:
        if task_id is not None:
            return f"{self.base_url}/tasks/{task_id}/jobs/{job_id}"
        return f"{self.base_url}/jobs/{job_id}"
