from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import LabelStudioFieldName


@dataclass
class ParsedObject:
    label: str
    bbox: list[float] | None = None
    polygon: list[list[float]] | None = None
    source: str = "human_confirmed"


@dataclass
class ParsedAnnotation:
    task_id: int
    image_id: str
    filename: str
    width: int
    height: int
    objects: list[ParsedObject]


def _percent_to_pixel(value: float, total: int) -> float:
    return round((value / 100.0) * total, 4)


def _parse_rectangle(result: dict[str, object], image_width: int, image_height: int) -> ParsedObject:
    value = result.get("value", {})
    if not isinstance(value, dict):
        raise ValueError("Rectangle result value is invalid.")
    labels = value.get("rectanglelabels", [])
    if not isinstance(labels, list) or not labels:
        raise ValueError("Rectangle labels are missing.")

    x = float(value.get("x", 0))
    y = float(value.get("y", 0))
    width = float(value.get("width", 0))
    height = float(value.get("height", 0))
    return ParsedObject(
        label=str(labels[0]),
        bbox=[
            _percent_to_pixel(x, image_width),
            _percent_to_pixel(y, image_height),
            _percent_to_pixel(width, image_width),
            _percent_to_pixel(height, image_height),
        ],
    )


def _parse_polygon(result: dict[str, object], image_width: int, image_height: int) -> ParsedObject:
    value = result.get("value", {})
    if not isinstance(value, dict):
        raise ValueError("Polygon result value is invalid.")
    labels = value.get("polygonlabels", [])
    if not isinstance(labels, list) or not labels:
        raise ValueError("Polygon labels are missing.")
    points = value.get("points", [])
    if not isinstance(points, list):
        raise ValueError("Polygon points are missing.")

    polygon: list[list[float]] = []
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            continue
        polygon.append(
            [
                _percent_to_pixel(float(point[0]), image_width),
                _percent_to_pixel(float(point[1]), image_height),
            ]
        )

    return ParsedObject(label=str(labels[0]), polygon=polygon)


def parse_human_annotation_task(
    *,
    remote_task: dict[str, object],
    image_id: str,
    filename: str,
    width: int,
    height: int,
) -> ParsedAnnotation | None:
    annotations = remote_task.get("annotations", [])
    if not isinstance(annotations, list) or not annotations:
        return None

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
        return None

    task_id = remote_task.get("id")
    if not isinstance(task_id, int):
        raise ValueError("Label Studio task id is missing.")

    objects: list[ParsedObject] = []
    for result in human_annotation.get("result", []):
        if not isinstance(result, dict):
            continue
        result_type = result.get("type")
        from_name = result.get("from_name")
        if result_type == "rectanglelabels" and from_name == LabelStudioFieldName.BBOX.value:
            objects.append(_parse_rectangle(result, width, height))
        elif result_type == "polygonlabels" and from_name == LabelStudioFieldName.LESION_POLYGON.value:
            objects.append(_parse_polygon(result, width, height))

    if not objects:
        return None

    return ParsedAnnotation(
        task_id=task_id,
        image_id=image_id,
        filename=filename,
        width=width,
        height=height,
        objects=objects,
    )
