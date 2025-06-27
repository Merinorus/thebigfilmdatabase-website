import logging
from urllib.parse import urljoin

import httpx

from app.config import settings
from app.constants import FILM_IMAGE_DIR_URL

logger = logging.getLogger(__name__)
_image_cdn_base_url = settings.FILM_IMAGE_CDN_BASE_URLS[0]


def image_cdn_base_url():
    return str(_image_cdn_base_url)


def get_film_image_url(image: str, *, cdn_enable=settings.FILM_IMAGE_CDN_ENABLE, base_url=None):
    base_url = base_url or image_cdn_base_url() if cdn_enable else str(FILM_IMAGE_DIR_URL)
    return str(urljoin(base_url, image))


async def update_cdn_url():
    global _image_cdn_base_url
    from app.core.database import db_ram_connection

    # Get a sample image path from the database
    cursor = db_ram_connection.cursor()
    cursor.execute("SELECT picture FROM films WHERE picture IS NOT NULL ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()
    if not row:
        return  # No images in DB

    image = row[0]

    async with httpx.AsyncClient() as client:
        for base_url in settings.FILM_IMAGE_CDN_BASE_URLS:
            image_url = urljoin(str(base_url), image)
            try:
                response = await client.head(image_url, timeout=5.0)
                response.raise_for_status()
                if base_url != _image_cdn_base_url:
                    logger.warning(f"Could not get images from CDN '{_image_cdn_base_url}'. Switching to '{base_url}'.")
                    _image_cdn_base_url = base_url
                return
            except (httpx.RequestError, httpx.HTTPStatusError):
                continue
