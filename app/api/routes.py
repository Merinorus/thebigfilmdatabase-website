from typing import Annotated

from fastapi import APIRouter, Depends, Path
from fastapi.exceptions import HTTPException

from app.api.schemas.response import BaseResponse, FilmListResponse, FilmResponse
from app.core import film
from app.core.schemas.query import SearchFilmQuery

api = APIRouter(
    prefix="/api",
    tags=["API"],
    responses={404: {"description": "Not found!"}},
)


@api.get("/health")
async def healthcheck():
    return BaseResponse()


@api.get("/search", response_model=FilmListResponse, response_model_exclude_none=True)
async def search(query: Annotated[SearchFilmQuery, Depends(SearchFilmQuery)]):
    films = film.search(
        dx_extract=query.dx_extract,
        dx_full=query.dx_full,
        name=query.name,
        manufacturer=query.manufacturer,
        limit=query.limit,
    )

    return FilmListResponse(data=films)


@api.get("/film/{url_name}", response_model=FilmResponse, response_model_exclude_none=True)
async def get_by_url_name(
    url_name: Annotated[str, Path(description="Unique URL-safe name of the film", max_length=255)],
):
    result = film.get_by_url(url_name)
    if not result:
        raise HTTPException(status_code=404, detail="Film not found")
    return FilmResponse(data=result)
