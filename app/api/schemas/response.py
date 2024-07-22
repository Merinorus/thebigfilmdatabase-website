from typing import Any

from pydantic import BaseModel

from app.core.schemas.film import FilmInDB


class BaseResponse(BaseModel):
    status: str = "ok"


class Response(BaseResponse):
    data: Any | None = None


class FilmResponse(Response):
    data: FilmInDB


class FilmListResponse(Response):
    data: list[FilmInDB] = None
