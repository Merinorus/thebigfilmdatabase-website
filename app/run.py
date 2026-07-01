import os

import uvicorn

from app.config import settings

uvicorn.run(
    "app.app:app",
    host=os.getenv("HOST", "0.0.0.0"),  # nosec B104
    port=int(os.getenv("PORT", "3500")),
    log_config=os.getenv("LOG_CONFIG", "log_conf.json"),
    proxy_headers=bool(settings.TRUSTED_PROXIES),
    forwarded_allow_ips=settings.TRUSTED_PROXIES,
)
