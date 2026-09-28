from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas.film import FilmInDB


class BaseResponse(BaseModel):
    status: str = "ok"


class Response(BaseResponse):
    data: Any | None = None


class FilmResponse(Response):
    data: FilmInDB


class FilmListResponse(Response):
    data: list[FilmInDB] = None


class FilmSuggestions(BaseModel):
    suggestions: list[FilmInDB]


class FilmNotFoundResponse(Response):
    status: Literal["error"] = "error"
    data: FilmSuggestions


class PaginatedFilmListResponse(FilmListResponse):
    page: int = Field(ge=1, description="Current page, starting at 1")
    limit: int = Field(ge=1, description="Maximum number of films per page")
    total: int = Field(ge=0, description="Total number of films matching the filters")
    pages: int = Field(ge=1, description="Total number of pages; 1 when no films match")


class AutocompleteResponse(Response):
    data: list[str] = []
