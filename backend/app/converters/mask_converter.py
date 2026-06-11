from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.converters.label_studio_parser import ParsedAnnotation


def write_mask_png(annotation: ParsedAnnotation, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask = Image.new("L", (annotation.width, annotation.height), 0)
    draw = ImageDraw.Draw(mask)

    for obj in annotation.objects:
        if obj.polygon:
            polygon = [(point[0], point[1]) for point in obj.polygon]
            if polygon:
                draw.polygon(polygon, fill=255)

    mask.save(output_path)
