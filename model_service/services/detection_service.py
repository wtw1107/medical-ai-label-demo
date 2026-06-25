from schemas import DetectionPredictRequest, DetectionPredictResponse, DetectionResult
from utils.geometry import clamp_bbox, default_detection_bbox
from utils.image_loader import try_load_image_info


class MockDetectionService:
    model_version = "v0.1"
    model_type = "detection"

    def predict(
        self,
        request: DetectionPredictRequest,
    ) -> DetectionPredictResponse:
        image_info = try_load_image_info(request.image_url)
        bbox = default_detection_bbox(image_info.width, image_info.height)
        bbox = clamp_bbox(bbox, image_info.width, image_info.height)

        return DetectionPredictResponse(
            model_id=request.model_id,
            model_version=self.model_version,
            model_type=self.model_type,
            results=[
                DetectionResult(
                    label="病灶",
                    bbox=bbox,
                    score=0.91,
                )
            ],
        )
