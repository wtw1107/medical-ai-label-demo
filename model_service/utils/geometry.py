def default_detection_bbox(width: int, height: int) -> list[int]:
    if width >= 240 and height >= 180:
        return [120, 80, 164, 148]

    left = max(0, int(width * 0.2))
    top = max(0, int(height * 0.2))
    right = max(left + 1, int(width * 0.7))
    bottom = max(top + 1, int(height * 0.7))
    return [left, top, right, bottom]


def clamp_bbox(bbox: list[int], width: int, height: int) -> list[int]:
    left, top, right, bottom = bbox
    max_x = max(0, width - 1)
    max_y = max(0, height - 1)

    left = min(max(left, 0), max_x)
    top = min(max(top, 0), max_y)
    right = min(max(right, left + 1), width)
    bottom = min(max(bottom, top + 1), height)
    return [left, top, right, bottom]


def bbox_to_polygon(bbox: list[int]) -> list[list[int]]:
    left, top, right, bottom = bbox
    return [
        [left, top],
        [right, top],
        [right, bottom],
        [left, bottom],
    ]


def default_segmentation_polygon(width: int, height: int) -> list[list[int]]:
    if width >= 240 and height >= 180:
        return [
            [120, 80],
            [240, 80],
            [240, 180],
            [120, 180],
        ]

    return [
        [max(0, int(width * 0.2)), max(0, int(height * 0.2))],
        [max(1, int(width * 0.75)), max(0, int(height * 0.2))],
        [max(1, int(width * 0.75)), max(1, int(height * 0.75))],
        [max(0, int(width * 0.2)), max(1, int(height * 0.75))],
    ]


def clamp_polygon(
    polygon: list[list[int]],
    width: int,
    height: int,
) -> list[list[int]]:
    max_x = max(0, width - 1)
    max_y = max(0, height - 1)
    clamped_points: list[list[int]] = []

    for x, y in polygon:
        clamped_points.append(
            [
                min(max(x, 0), max_x),
                min(max(y, 0), max_y),
            ]
        )

    return clamped_points
