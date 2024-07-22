from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import api
from app.config import settings
from app.constants import STATIC_DIR
from app.website.routes import website

app = FastAPI(title="The Big Film Database")


# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int, window_seconds: int):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_counts = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = datetime.now()

        # Cleanup old requests
        self.request_counts[client_ip] = [
            request_time
            for request_time in self.request_counts[client_ip]
            if current_time - request_time < timedelta(seconds=self.window_seconds)
        ]

        if len(self.request_counts[client_ip]) >= self.max_requests:
            return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})

        # Record the new request
        self.request_counts[client_ip].append(current_time)
        response = await call_next(request)
        return response


# Add the rate limiter middleware to the app
app.add_middleware(
    RateLimiterMiddleware,
    max_requests=settings.RATE_LIMITER_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMITER_TIME_WINDOW,
)

app.include_router(website)
app.include_router(api)
