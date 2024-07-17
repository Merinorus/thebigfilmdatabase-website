from typing import Any

from pydantic import BaseModel


class BaseResponse(BaseModel):
    status: str = "ok"


class Response(BaseResponse):
    data: Any | None = None
