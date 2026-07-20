# CVAT Video Flow Audit

Date: 2026-07-20  
Branch: feature/native-video-platform  
Decision: keep historical CVAT compatibility code, but new video tasks use `annotation_backend=native` and enter the platform native workbench.

## Creation

- `backend/app/routers/videos.py`
  - `POST /api/video-datasets/upload` accepted `annotation_backend`.
  - Before this MVP change, `annotation_backend=cvat` triggered a CVAT health check for new video tasks.
  - The route still allows `cvat` for legacy compatibility, but the default is now `native`.
- `backend/app/services/video_storage_service.py`
  - `VideoStorageService.upload_video_dataset()` persisted `Dataset.annotation_backend`.
  - Historical allowed values were `cvat` and `label_studio`.
  - The allowed set is now `native`, `cvat`, and `label_studio`; default is `native`.
- `backend/app/services/cvat_service.py`
  - `CvatService.init_dataset()` creates or reuses a CVAT project and one CVAT task per video.
  - Internal creation helpers are `_create_project()`, `_create_task()`, and `_upload_video_to_task()`.
  - This service is retained for historical datasets and is not called by the new native video upload path.

## Jump / Access

- `frontend/src/pages/UploadPage.tsx`
  - Before this MVP change, video uploads submitted `annotation_backend: "cvat"`.
  - The upload page now submits `annotation_backend: "native"` and describes the platform native workbench.
- `frontend/src/pages/VideoDatasetDetailPage.tsx`
  - Historical CVAT entry uses `handleOpenCvat()` and `getCvatAccess()` to open a CVAT job URL.
  - Native datasets now display `进入原生标注`, linking to `/video-datasets/:datasetId/videos/:videoId/native-workbench`.
  - CVAT health/access calls are only made when `annotation_backend === "cvat"`.
- `frontend/src/pages/TaskListPage.tsx`
  - Video tasks are now classified as `原生视频工作台`, `CVAT 历史兼容`, or `Label Studio 旧版`.
  - New native video tasks no longer display as CVAT tasks.

## Status Sync

- `backend/app/routers/videos.py`
  - `POST /api/video-datasets/{dataset_id}/cvat/sync` remains available.
  - `GET /api/videos/{video_id}/cvat/annotations-summary` remains available.
  - `GET /api/videos/{video_id}/cvat/access` remains available.
- `backend/app/services/cvat_service.py`
  - `sync_dataset()` refreshes CVAT task/job state for historical CVAT datasets.
  - `_refresh_video_mapping()` reads CVAT task and job state and stores `cvat_status`, `cvat_job_id`, URLs, and `cvat_annotation_updated_at`.
  - `_parse_video_annotations()` reads CVAT tags, polygons, and issues for summary/export.
- Native MVP state is currently kept in browser localStorage by `NativeVideoWorkbenchPage` for refresh recovery. Formal backend persistence remains next-phase work.

## Export

- `backend/app/routers/videos.py`
  - `POST /api/video-datasets/{dataset_id}/exports/cvat-bline-test` remains for historical CVAT exports.
  - `POST /api/video-datasets/{dataset_id}/exports/bline-keyframes` remains for keyframe Label Studio exports.
  - `GET /api/video-exports/{export_id}/download` remains the shared download endpoint.
- `backend/app/services/cvat_service.py`
  - `export_bline_test()` exports CVAT B-line polygons and masks into a zip bundle.
- `backend/app/services/video_keyframe_export_service.py`
  - Existing keyframe export is retained.
- Native full export is not expanded in this P0; the existing export code is preserved.

## Protected Flows

- Image tasks still use `backend/app/routers/tasks.py`, `LabelStudioService`, `frontend/src/pages/TaskDetailPage.tsx`, and `frontend/src/components/WorkbenchPanel.tsx`.
- No Label Studio image-task API signatures were changed.
- Historical CVAT service code was not deleted.
