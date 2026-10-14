import logging

import httpx
from fastapi import FastAPI

from app.config import settings

logger = logging.getLogger(__name__)


async def update_alternative_interface_availability(app: FastAPI):
    error = "The response is not the application page."
    try:
        async with httpx.AsyncClient() as client:
            # Do not follow redirects: a login page should not enable the promotion.
            response = await client.get(
                str(settings.ALTERNATIVE_INTERFACE_URL),
                timeout=5.0,
                follow_redirects=False,
                headers={"Cache-Control": "no-cache"},
            )
        response.raise_for_status()
        # Check if there is a React application responding.
        # It's a bit hacky, a "health" route ought to be written.
        available = response.status_code == 200 and any(
            marker in response.text for marker in ('<div id="root">', "<div id='root'>")
        )
    except httpx.HTTPError as e:
        error = str(e)
        available = False
    if available != getattr(app.state, "alternative_interface_available", None):
        if available:
            logger.warning("Alternative interface is available: %s", settings.ALTERNATIVE_INTERFACE_URL)
        else:
            logger.warning("Error with alternative interface: %s\n%s", settings.ALTERNATIVE_INTERFACE_URL, error)
    app.state.alternative_interface_available = available
