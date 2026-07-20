# MedSAM2 Service API v1

Status: frozen for first-stage MVP  
Owner: platform native video workbench  
Date: 2026-07-20  
Scope: local staging MedSAM2 service and platform Mock client must use the same request and response shapes.

## Common Rules

- Base URL is provided by platform configuration; the platform frontend must not call the model service directly in production.
- Frame indices are zero-based.
- Coordinates use original video pixel coordinates.
- Point prompt format is `[x, y]`.
- Box prompt format is `[x1, y1, x2, y2]`.
- Positive point label is `1`; negative point label is `0`.
- `video_ref` is a relative or platform-issued media reference. Do not expose absolute server paths.
- API boundary mask format is normalized RLE. Do not return tensors, GPU objects, pickle data, or raw CUDA memory references.
- `object_id` must remain stable within one video.
- Async task status values are `queued`, `initializing`, `running`, `cancelling`, `cancelled`, `completed`, `failed`.
- Errors return `error_code` and `message`; messages must not include passwords, tokens, full environment variables, patient identity, or absolute data paths.

## RLE Mask

`mask.size` is `[height, width]`. `mask.counts` is row-major run length encoding that starts with the count of zero-valued pixels, then alternates one-valued and zero-valued runs.

```json
{
  "size": [480, 640],
  "counts": [1200, 34, 601, 41],
  "order": "row-major"
}
```

## GET /health

Returns service readiness without loading patient data.

Response:

```json
{
  "status": "ok",
  "service": "medsam2",
  "version": "v1",
  "model_loaded": true,
  "device": "cuda:0",
  "supports": {
    "predict_frame": true,
    "propagate": true,
    "cancel": true
  }
}
```

## POST /initialize

Initializes or reuses a video session.

Request:

```json
{
  "task_id": "platform-task-or-dataset-id",
  "video_id": "video-id",
  "session_id": "native-video-session-id",
  "video_ref": "video_datasets/<dataset_id>/videos/<file>",
  "frame_count": 120,
  "width": 640,
  "height": 480,
  "fps": 25.0
}
```

Response:

```json
{
  "session_id": "native-video-session-id",
  "video_id": "video-id",
  "status": "completed",
  "frame_count": 120,
  "width": 640,
  "height": 480
}
```

## POST /predict-frame

Generates a mask for one object on one frame from prompts. The first-stage platform MVP uses the same shape for Mock and Real responses.

Request:

```json
{
  "task_id": "platform-task-or-dataset-id",
  "video_id": "video-id",
  "session_id": "native-video-session-id",
  "video_ref": "video_datasets/<dataset_id>/videos/<file>",
  "frame_index": 0,
  "object_id": "obj-001",
  "prompts": [
    {
      "type": "point",
      "label": 1,
      "point": [320, 240]
    },
    {
      "type": "point",
      "label": 0,
      "point": [120, 80]
    },
    {
      "type": "box",
      "box": [250, 170, 390, 310]
    }
  ]
}
```

Response:

```json
{
  "request_id": "predict-uuid",
  "session_id": "native-video-session-id",
  "video_id": "video-id",
  "frame_index": 0,
  "object_id": "obj-001",
  "mask": {
    "size": [480, 640],
    "counts": [1200, 34, 601, 41],
    "order": "row-major"
  },
  "score": 0.91,
  "backend": "real",
  "status": "completed"
}
```

## POST /propagate

Starts short-range propagation from a prompted frame. First-stage integration may defer this endpoint; the contract is reserved so platform and service code do not diverge.

Request:

```json
{
  "task_id": "platform-task-or-dataset-id",
  "video_id": "video-id",
  "session_id": "native-video-session-id",
  "video_ref": "video_datasets/<dataset_id>/videos/<file>",
  "object_id": "obj-001",
  "start_frame": 0,
  "end_frame": 10,
  "direction": "forward"
}
```

Response:

```json
{
  "job_id": "propagate-uuid",
  "session_id": "native-video-session-id",
  "video_id": "video-id",
  "object_id": "obj-001",
  "status": "queued"
}
```

## GET /propagate/{job_id}

Response:

```json
{
  "job_id": "propagate-uuid",
  "status": "running",
  "progress": {
    "completed_frames": 4,
    "total_frames": 10
  },
  "results": [
    {
      "frame_index": 0,
      "mask": {
        "size": [480, 640],
        "counts": [1200, 34, 601, 41],
        "order": "row-major"
      },
      "score": 0.91
    }
  ],
  "error": null
}
```

## POST /propagate/{job_id}/cancel

Response:

```json
{
  "job_id": "propagate-uuid",
  "status": "cancelling"
}
```

## POST /sessions/{session_id}/release

Releases model-side caches for one video session.

Response:

```json
{
  "session_id": "native-video-session-id",
  "status": "completed"
}
```

## Error Shape

```json
{
  "error_code": "MODEL_NOT_READY",
  "message": "MedSAM2 model is not loaded.",
  "request_id": "predict-uuid"
}
```
