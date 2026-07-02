from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_SERVICE_DIR = PROJECT_ROOT / "model_service"
if str(MODEL_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_SERVICE_DIR))

from services.roboflow_thyroid_detection_service import (  # noqa: E402
    RoboflowThyroidDetectionService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Roboflow thyroid detection against a local image.",
    )
    parser.add_argument(
        "--image",
        default="samples/dino_detection/sample_001.png",
        help="Image path relative to project root or absolute path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path = Path(args.image)
    if not image_path.is_absolute():
        image_path = (PROJECT_ROOT / image_path).resolve()

    try:
        service = RoboflowThyroidDetectionService()
        result = service.predict_image(image_path, include_raw=True)
    except Exception as exc:
        print(str(exc))
        return 1

    predictions = result.get("predictions", [])
    first_prediction = predictions[0] if predictions else None
    raw = result.get("raw", {})
    raw_predictions = raw.get("predictions", []) if isinstance(raw, dict) else []
    first_raw_prediction = raw_predictions[0] if raw_predictions else None

    print(f"image_path={image_path}")
    print(f"confidence={os.getenv('ROBOFLOW_CONFIDENCE', '0.25')}")
    print(result["model_id"])
    print(result["model_version"])
    print(result["model_type"])
    print(len(predictions))
    print(f"raw_keys={sorted(raw.keys()) if isinstance(raw, dict) else []}")
    print(f"raw_prediction_count={len(raw_predictions)}")
    print("first_raw_prediction=")
    print(json.dumps(first_raw_prediction, ensure_ascii=False, indent=2))
    print("first_detection=")
    print(json.dumps(first_prediction, ensure_ascii=False, indent=2))
    print("platform_result=")
    print(
        json.dumps(
            {
                "model_id": result["model_id"],
                "model_version": result["model_version"],
                "model_type": result["model_type"],
                "predictions": predictions,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
