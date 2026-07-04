from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.exceptions import HTTPException

from app.api.schemas.response import AutocompleteResponse, BaseResponse, FilmListResponse, FilmResponse
from app.core import film
from app.core.film import MAX_AUTOCOMPLETE_RESULTS, MAX_RESULTS
from app.core.schemas.query import SearchFilmQuery

api = APIRouter(
    prefix="/api",
    tags=["API"],
    responses={404: {"description": "Not found!"}},
)

# Autocomplete responses depend only on the query and change rarely (data/stopword tweaks), so let
# browsers and shared caches (CDN/proxy) keep them: fresh for a day, then served stale for up to a
# month while the cache revalidates in the background (one slightly outdated hit is harmless here).
AUTOCOMPLETE_CACHE_CONTROL = "public, max-age=86400, stale-while-revalidate=2592000"
# Search and film-detail responses: short freshness to cap origin load during traffic spikes (a CDN
# edge hits the origin at most ~once per 10 min per query/film), with a long stale window so the
# cache keeps serving instantly. The rate limiter remains the backstop against cache-busting abuse.
SEARCH_FILM_CACHE_CONTROL = "public, max-age=600, stale-while-revalidate=2592000"


# Also allow HEAD: uptime monitors (UptimeRobot...) probe with HEAD, and FastAPI — unlike plain
# Starlette — does not auto-add HEAD to GET routes (see fastapi/fastapi#1773), so a bare @api.get
# would answer HEAD with 405.
@api.api_route("/health", methods=["GET", "HEAD"])
async def healthcheck():
    return BaseResponse()


@api.get("/search", response_model=FilmListResponse, response_model_exclude_none=True)
async def search(response: Response, query: Annotated[SearchFilmQuery, Depends(SearchFilmQuery)]):
    response.headers["Cache-Control"] = SEARCH_FILM_CACHE_CONTROL
    films = film.search(
        dx_extract=query.dx_extract,
        dx_full=query.dx_full,
        name=query.name,
        manufacturer=query.manufacturer,
        limit=query.limit,
    )

    return FilmListResponse(data=films)


@api.get("/random", response_model=FilmListResponse, response_model_exclude_none=True)
async def random(
    limit: Annotated[int, Query(ge=1, le=MAX_RESULTS, description="Number of random films to return")] = 1,
):
    films = film.get_random(limit=limit)
    return FilmListResponse(data=films)


@api.get("/autocomplete/name", response_model=AutocompleteResponse)
async def autocomplete_name(
    response: Response,
    q: Annotated[str, Query(max_length=255, description="Partial film name; only its last word is completed")],
    limit: Annotated[
        int, Query(ge=1, le=MAX_AUTOCOMPLETE_RESULTS, description="Max number of suggestions")
    ] = MAX_AUTOCOMPLETE_RESULTS,
):
    response.headers["Cache-Control"] = AUTOCOMPLETE_CACHE_CONTROL
    suggestions = film.autocomplete(column="name", text=q, limit=limit)
    return AutocompleteResponse(data=suggestions)


@api.get("/autocomplete/manufacturer", response_model=AutocompleteResponse)
async def autocomplete_manufacturer(
    response: Response,
    q: Annotated[str, Query(max_length=255, description="Partial manufacturer; only its last word is completed")],
    limit: Annotated[
        int, Query(ge=1, le=MAX_AUTOCOMPLETE_RESULTS, description="Max number of suggestions")
    ] = MAX_AUTOCOMPLETE_RESULTS,
):
    response.headers["Cache-Control"] = AUTOCOMPLETE_CACHE_CONTROL
    suggestions = film.autocomplete(column="manufacturer", text=q, limit=limit)
    return AutocompleteResponse(data=suggestions)


@api.get("/film/{url_name}", response_model=FilmResponse, response_model_exclude_none=True)
async def get_by_url_name(
    response: Response,
    url_name: Annotated[str, Path(description="Unique URL-safe name of the film", max_length=255)],
):
    response.headers["Cache-Control"] = SEARCH_FILM_CACHE_CONTROL
    result = film.get_by_url(url_name)
    if not result:
        raise HTTPException(status_code=404, detail="Film not found")
    return FilmResponse(data=result)
