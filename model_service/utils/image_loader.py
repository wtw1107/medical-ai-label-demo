from io import BytesIO

import httpx
from PIL import Image

from schemas import ImageInfo


def try_load_image_info(image_url: str) -> ImageInfo:
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, trust_env=False) as client:
            response = client.get(image_url)
            response.raise_for_status()

        with Image.open(BytesIO(response.content)) as image:
            width, height = image.size
    except Exception:
        return ImageInfo(width=512, height=512, source="fallback")

    return ImageInfo(width=width, height=height, source="remote")
