from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from limits import RateLimitItemPerSecond
from limits.storage import MemoryStorage
from limits.strategies import SlidingWindowCounterRateLimiter

from app.api.routes import api
from app.config import settings
from app.constants import STATIC_DIR
from app.website.routes import website

app = FastAPI(title="The Big Film Database")


# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
