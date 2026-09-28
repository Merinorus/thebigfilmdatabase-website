import logging
from urllib.parse import quote, urljoin

import httpx

from app.config import settings
from app.constants import FILM_IMAGE_DIR_URL
from app.utils.image_path import safe_image_filename

logger = logging.getLogger(__name__)
_image_cdn_base_url = settings.FILM_IMAGE_CDN_BASE_URLS[0]


def image_cdn_base_url():
    return str(_image_cdn_base_url)


def get_film_image_url(image: str, *, cdn_enable=settings.FILM_IMAGE_CDN_ENABLE, base_url=None):
    if safe_image_filename(image) is None:
        return None
    base_url = base_url or image_cdn_base_url() if cdn_enable else str(FILM_IMAGE_DIR_URL)
    return str(urljoin(base_url, quote(image, safe="")))


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
    if safe_image_filename(image) is None:
        return

    async with httpx.AsyncClient() as client:
        for base_url in settings.FILM_IMAGE_CDN_BASE_URLS:
            image_url = get_film_image_url(image, cdn_enable=True, base_url=str(base_url))
            try:
                response = await client.get(image_url, timeout=5.0, follow_redirects=True)
                response.raise_for_status()
                if base_url != _image_cdn_base_url:
                    logger.warning(f"Switching CDN base URL from '{_image_cdn_base_url}' to '{base_url}'.")
                    _image_cdn_base_url = base_url
                return
            except httpx.HTTPError as e:
                logger.warning(f"Error with this CDN: {base_url}\n{e}")
                continue
