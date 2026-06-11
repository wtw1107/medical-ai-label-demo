from schemas import (
    SegmentationPredictRequest,
    SegmentationPredictResponse,
    SegmentationResult,
)
from utils.geometry import (
    clamp_polygon,
    default_segmentation_polygon,
)
from utils.image_loader import try_load_image_info


class MockSegmentationService:
    model_version = "v0.1"

    def predict(
        self,
        request: SegmentationPredictRequest,
    ) -> SegmentationPredictResponse:
        image_info = try_load_image_info(request.image_url)
        polygon = clamp_polygon(
            default_segmentation_polygon(image_info.width, image_info.height),
            image_info.width,
            image_info.height,
        )

        return SegmentationPredictResponse(
            model_id=request.model_id,
            model_version=self.model_version,
            results=[
                SegmentationResult(
                    label="病灶轮廓",
                    polygon=polygon,
                    score=0.86,
                )
            ],
        )
