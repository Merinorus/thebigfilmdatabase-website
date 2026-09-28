"""The upstream picture column is a raster filename, never an arbitrary URL."""

import re

_IMAGE_FILENAME = re.compile(r"[\w][\w .()+,&’'-]*\.(?:jpg|jpeg|png|gif|webp|avif)", re.IGNORECASE)


def safe_image_filename(value: str | None) -> str | None:
    if value and _IMAGE_FILENAME.fullmatch(value):
        return value
    return None
