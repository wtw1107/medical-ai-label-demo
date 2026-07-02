from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.constants import LabelStudioFieldName, TaskType


@dataclass
class PredictionBundle:
    model_version: str
    score: float
    results: list[dict[str, object]]


def _build_result_meta(
    *,
    model_id: str,
    model_version: str,
    model_type: str,
    extra_meta: dict[str, object] | None = None,
) -> dict[str, object]:
    meta = dict(extra_meta or {})
    meta.update(
        {
            "model_id": model_id,
            "model_version": model_version,
            "model_type": model_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return meta


def _normalize_result_meta(meta: object) -> dict[str, object] | None:
    if isinstance(meta, dict):
        return {str(key): value for key, value in meta.items()}
    return None


def _normalize_bbox_payload(bbox: object) -> list[float]:
    if isinstance(bbox, list):
        if len(bbox) != 4:
            raise ValueError("BBox must contain four numeric values.")
        return [float(value) for value in bbox]
    if isinstance(bbox, dict):
        try:
            return [
                float(bbox["x"]),
                float(bbox["y"]),
                float(bbox["width"]),
                float(bbox["height"]),
            ]
        except KeyError as exc:
            raise ValueError("BBox dict must contain x, y, width and height.") from exc
    raise ValueError("BBox must be either a four-value list or a dict payload.")


def _first_result(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        raise ValueError("Prediction result payload is invalid.")
    return result


def _extract_score(result: dict[str, object]) -> float:
    score = result.get("score")
    if not isinstance(score, (int, float)):
        raise ValueError("Prediction result score is missing.")
    return float(score)


def _extract_bbox(result: dict[str, object]) -> list[float]:
    return _normalize_bbox_payload(result.get("bbox"))


def _extract_polygon(result: dict[str, object]) -> list[list[float]]:
    polygon = result.get("polygon")
    if not isinstance(polygon, list):
        raise ValueError("Polygon result is missing.")
    normalized_polygon: list[list[float]] = []
    for point in polygon:
        if not isinstance(point, list) or len(point) != 2:
            continue
        normalized_polygon.append([float(point[0]), float(point[1])])
    if not normalized_polygon:
        raise ValueError("Polygon result does not contain any valid points.")
    return normalized_polygon


def build_bbox_prediction(
    *,
    bbox: list[float],
    label_name: str,
    image_width: int,
    image_height: int,
    score: float,
    model_id: str,
    model_version: str,
    extra_meta: dict[str, object] | None = None,
) -> dict[str, object]:
    x, y, width, height = _normalize_bbox(bbox, image_width, image_height)
    return {
        "from_name": LabelStudioFieldName.BBOX.value,
        "to_name": LabelStudioFieldName.IMAGE.value,
        "type": "rectanglelabels",
        "value": {
            "x": _clamp_percent((x / image_width) * 100),
            "y": _clamp_percent((y / image_height) * 100),
            "width": _clamp_percent((width / image_width) * 100),
            "height": _clamp_percent((height / image_height) * 100),
            "rectanglelabels": [label_name],
        },
        "score": score,
        "meta": _build_result_meta(
            model_id=model_id,
            model_version=model_version,
            model_type="detection",
            extra_meta=extra_meta,
        ),
    }


def build_polygon_prediction(
    *,
    polygon: list[list[float]],
    label_name: str,
    image_width: int,
    image_height: int,
    score: float,
    model_id: str,
    model_version: str,
    extra_meta: dict[str, object] | None = None,
) -> dict[str, object]:
    points = [
        [
            _clamp_percent((point[0] / image_width) * 100),
            _clamp_percent((point[1] / image_height) * 100),
        ]
        for point in polygon
    ]
    return {
        "from_name": LabelStudioFieldName.LESION_POLYGON.value,
        "to_name": LabelStudioFieldName.IMAGE.value,
        "type": "polygonlabels",
        "value": {
            "points": points,
            "polygonlabels": [label_name],
        },
        "score": score,
        "meta": _build_result_meta(
            model_id=model_id,
            model_version=model_version,
            model_type="segmentation",
            extra_meta=extra_meta,
        ),
    }


def _clamp_percent(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def _normalize_bbox(bbox: list[float], image_width: int, image_height: int) -> tuple[float, float, float, float]:
    if len(bbox) != 4:
        raise ValueError("BBox must contain four numeric values.")

    x1, y1, x2_or_width, y2_or_height = bbox
    if x2_or_width > x1 and y2_or_height > y1 and x2_or_width <= image_width and y2_or_height <= image_height:
        width = x2_or_width - x1
        height = y2_or_height - y1
        return x1, y1, width, height

    return x1, y1, x2_or_width, y2_or_height


def build_prediction_bundle(
    *,
    task_type: str,
    label_name: str,
    image_width: int,
    image_height: int,
    detection: dict[str, object] | None = None,
    segmentation: dict[str, object] | None = None,
) -> PredictionBundle:
    results: list[dict[str, object]] = []
    versions: list[str] = []
    scores: list[float] = []

    if task_type in {TaskType.BBOX.value, TaskType.BBOX_POLYGON.value} and detection:
        det_results = detection.get("results")
        if not isinstance(det_results, list) or not det_results:
            det_results = []
        if det_results:
            det_result = _first_result(det_results[0])
            detection_score = _extract_score(det_result)
            results.append(
                build_bbox_prediction(
                    bbox=_extract_bbox(det_result),
                    label_name=label_name,
                    image_width=image_width,
                    image_height=image_height,
                    score=detection_score,
                    model_id=str(detection["model_id"]),
                    model_version=str(detection["model_version"]),
                    extra_meta=_normalize_result_meta(det_result.get("meta")),
                )
            )
            versions.append(str(detection["model_version"]))
            scores.append(detection_score)

    if task_type in {TaskType.POLYGON.value, TaskType.BBOX_POLYGON.value} and segmentation:
        seg_results = segmentation.get("results")
        if not isinstance(seg_results, list) or not seg_results:
            seg_results = []
        if seg_results:
            seg_result = _first_result(seg_results[0])
            segmentation_score = _extract_score(seg_result)
            results.append(
                build_polygon_prediction(
                    polygon=_extract_polygon(seg_result),
                    label_name=label_name,
                    image_width=image_width,
                    image_height=image_height,
                    score=segmentation_score,
                    model_id=str(segmentation["model_id"]),
                    model_version=str(segmentation["model_version"]),
                    extra_meta=_normalize_result_meta(seg_result.get("meta")),
                )
            )
            versions.append(str(segmentation["model_version"]))
            scores.append(segmentation_score)

    if not results:
        raise ValueError("No prediction results were generated for this task.")

    if len(set(versions)) == 1:
        model_version = versions[0]
    else:
        model_version = " | ".join(versions)

    score = round(sum(scores) / len(scores), 4)
    return PredictionBundle(model_version=model_version, score=score, results=results)
