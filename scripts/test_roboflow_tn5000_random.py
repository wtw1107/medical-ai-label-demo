from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_SERVICE_DIR = PROJECT_ROOT / "model_service"
if str(MODEL_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_SERVICE_DIR))

from services.roboflow_thyroid_detection_service import (  # noqa: E402
    RoboflowThyroidDetectionService,
)


SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Randomly sample TN5000 images and validate Roboflow thyroid detection.",
    )
    parser.add_argument(
        "--image-dir",
        required=True,
        help="Root directory that contains TN5000 images.",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=10,
        help="Number of images to sample. Default: 10.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed. Default: 42.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=None,
        help="Optional confidence threshold that overrides ROBOFLOW_CONFIDENCE.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="Optional cap for scanned images before sampling.",
    )
    return parser.parse_args()


def collect_images(image_dir: Path, max_images: int | None) -> list[Path]:
    images: list[Path] = []
    for path in image_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        images.append(path)
        if max_images is not None and len(images) >= max_images:
            break
    return images


def serialize_detection(detection: dict[str, Any] | None) -> dict[str, Any] | None:
    if detection is None:
        return None
    return detection


def ensure_api_key() -> None:
    if os.getenv("ROBOFLOW_API_KEY"):
        return
    raise RuntimeError(
        "ROBOFLOW_API_KEY is not set. Please set it before running Roboflow thyroid detection."
    )


def main() -> int:
    args = parse_args()
    ensure_api_key()

    image_dir = Path(args.image_dir).expanduser().resolve()
    if not image_dir.exists() or not image_dir.is_dir():
        raise SystemExit(f"Image directory not found: {image_dir}")

    if args.confidence is not None:
        os.environ["ROBOFLOW_CONFIDENCE"] = str(args.confidence)

    scanned_images = collect_images(
        image_dir=image_dir,
        max_images=args.max_images,
    )
    if not scanned_images:
        raise SystemExit(f"No supported images found under: {image_dir}")

    sample_count = min(args.num_samples, len(scanned_images))
    sampler = random.Random(args.seed)
    sampled_images = sampler.sample(scanned_images, sample_count)

    service = RoboflowThyroidDetectionService()
    confidence = service.confidence

    print(f"image_dir={image_dir}")
    print(f"scanned_image_count={len(scanned_images)}")
    print(f"sample_count={sample_count}")
    print(f"confidence={confidence}")

    results: list[dict[str, Any]] = []
    total_raw_predictions = 0
    total_parsed_detections = 0
    api_error_count = 0
    api_success_count = 0
    api_success_but_raw_zero_count = 0
    raw_positive_but_filtered_zero_count = 0
    parsed_positive_count = 0
    best_image_path: str | None = None
    max_detections_in_one_image = 0

    for index, image_path in enumerate(sampled_images, start=1):
        try:
            result = service.predict_image(image_path, include_raw=True)
        except Exception as exc:
            api_error_count += 1
            item = {
                "image_path": str(image_path),
                "raw_prediction_count": 0,
                "parsed_detection_count": 0,
                "first_detection": None,
                "api_error": str(exc),
            }
            results.append(item)
            print(f"[{index}/{sample_count}] {image_path}")
            print("  api_error=" + str(exc))
            continue

        api_success_count += 1
        predictions = result.get("predictions", [])
        raw = result.get("raw", {})
        raw_predictions = raw.get("predictions", []) if isinstance(raw, dict) else []
        first_detection = predictions[0] if predictions else None

        parsed_count = len(predictions)
        raw_count = len(raw_predictions)
        total_raw_predictions += raw_count
        total_parsed_detections += parsed_count
        if raw_count == 0:
            api_success_but_raw_zero_count += 1
        elif parsed_count == 0:
            raw_positive_but_filtered_zero_count += 1
        else:
            parsed_positive_count += 1
        if parsed_count > max_detections_in_one_image:
            max_detections_in_one_image = parsed_count
            best_image_path = str(image_path)

        item = {
            "image_path": str(image_path),
            "raw_prediction_count": raw_count,
            "parsed_detection_count": parsed_count,
            "first_detection": serialize_detection(first_detection),
            "api_error": None,
        }
        results.append(item)

        print(f"[{index}/{sample_count}] {image_path}")
        print(f"  raw_prediction_count={raw_count}")
        print(f"  parsed_detection_count={parsed_count}")
        if first_detection is not None:
            print("  first_detection=" + json.dumps(first_detection, ensure_ascii=False))

    summary = {
        "image_dir": str(image_dir),
        "num_samples": sample_count,
        "seed": args.seed,
        "confidence": confidence,
        "tested_count": len(results),
        "api_error_count": api_error_count,
        "api_success_count": api_success_count,
        "api_success_but_raw_zero_count": api_success_but_raw_zero_count,
        "raw_positive_but_filtered_zero_count": raw_positive_but_filtered_zero_count,
        "parsed_positive_count": parsed_positive_count,
        "images_with_raw_predictions": sum(
            1 for item in results if item["raw_prediction_count"] > 0
        ),
        "images_with_parsed_detections": sum(
            1 for item in results if item["parsed_detection_count"] > 0
        ),
        "total_raw_predictions": total_raw_predictions,
        "total_parsed_detections": total_parsed_detections,
        "best_image_path": best_image_path,
        "max_detections_in_one_image": max_detections_in_one_image,
        "results": results,
    }

    print(f"tested_count={summary['tested_count']}")
    print(f"api_error_count={summary['api_error_count']}")
    print(f"api_success_count={summary['api_success_count']}")
    print(f"images_with_raw_predictions={summary['images_with_raw_predictions']}")
    print(f"images_with_parsed_detections={summary['images_with_parsed_detections']}")
    print(f"total_raw_predictions={summary['total_raw_predictions']}")
    print(f"total_parsed_detections={summary['total_parsed_detections']}")
    print(f"best_image_path={summary['best_image_path']}")
    print(f"max_detections_in_one_image={summary['max_detections_in_one_image']}")

    if api_error_count > 0:
        print("Some Roboflow API calls failed. Check api_error entries above.")
    elif total_parsed_detections == 0:
        print(
            "Roboflow API calls succeeded, but no sampled TN5000 images returned detections. "
            "Consider testing more images, lowering confidence, or using another model."
        )

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = (PROJECT_ROOT / output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"output={output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
