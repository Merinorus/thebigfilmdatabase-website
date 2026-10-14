import asyncio
import contextlib

from fastapi import FastAPI, Request
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from limits import RateLimitItemPerSecond
from limits.storage import MemoryStorage
from limits.strategies import SlidingWindowCounterRateLimiter

from app.api.routes import api
from app.config import settings
from app.constants import FILM_IMAGE_DIR_URL, STATIC_DIR, STATIC_DIR_URL
from app.core.alternative_interface import update_alternative_interface_availability
from app.core.cdn import update_cdn_url
from app.website.routes import website


async def periodically_update_availability(app: FastAPI):
    while True:
        await update_alternative_interface_availability(app)
        await asyncio.sleep(settings.ALTERNATIVE_INTERFACE_CHECK_INTERVAL)


async def daily_cdn_update():
    if settings.FILM_IMAGE_CDN_ENABLE:
        while True:
            # Rotate to another CDN if the current one is unavailable.
            await update_cdn_url()
            await asyncio.sleep(settings.FILM_IMAGE_CDN_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.alternative_interface_available = None
    tasks = [
        asyncio.create_task(daily_cdn_update()),
        asyncio.create_task(periodically_update_availability(app)),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="The Big Film Database", lifespan=lifespan)


# Mount static files
app.mount(STATIC_DIR_URL, StaticFiles(directory=STATIC_DIR), name="static")
if not settings.FILM_IMAGE_CDN_ENABLE:
    app.mount(FILM_IMAGE_DIR_URL, StaticFiles(directory=settings.FILM_IMAGE_DIR), name="film-images")

# Rate limiter
storage = MemoryStorage()
limiter = SlidingWindowCounterRateLimiter(storage)
rate_limit = RateLimitItemPerSecond(settings.RATE_LIMITER_MAX_REQUESTS, settings.RATE_LIMITER_TIME_WINDOW)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    if not limiter.hit(rate_limit, client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
    return await call_next(request)


app.include_router(website)
app.include_router(api)
