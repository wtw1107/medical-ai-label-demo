from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import LabelStudioFieldName, TaskType


@dataclass
class PredictionBundle:
    model_version: str
    score: float
    results: list[dict[str, object]]


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


def build_bbox_prediction(
    *,
    bbox: list[float],
    label_name: str,
    image_width: int,
    image_height: int,
    score: float,
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
    }


def build_polygon_prediction(
    *,
    polygon: list[list[float]],
    label_name: str,
    image_width: int,
    image_height: int,
    score: float,
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
    }


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
        det_result = detection["results"][0]
        results.append(
            build_bbox_prediction(
                bbox=det_result["bbox"],
                label_name=label_name,
                image_width=image_width,
                image_height=image_height,
                score=float(det_result["score"]),
            )
        )
        versions.append(str(detection["model_version"]))
        scores.append(float(det_result["score"]))

    if task_type in {TaskType.POLYGON.value, TaskType.BBOX_POLYGON.value} and segmentation:
        seg_result = segmentation["results"][0]
        results.append(
            build_polygon_prediction(
                polygon=seg_result["polygon"],
                label_name=label_name,
                image_width=image_width,
                image_height=image_height,
                score=float(seg_result["score"]),
            )
        )
        versions.append(str(segmentation["model_version"]))
        scores.append(float(seg_result["score"]))

    if not results:
        raise ValueError("No prediction results were generated for this task.")

    if len(set(versions)) == 1:
        model_version = versions[0]
    else:
        model_version = " | ".join(versions)

    score = round(sum(scores) / len(scores), 4)
    return PredictionBundle(model_version=model_version, score=score, results=results)
