import os
import random
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.routing import APIRoute
from fastapi.templating import Jinja2Templates

from app.constants import STATIC_DIR, TEMPLATE_DIR
from app.core import film
from app.core.database import total_count
from app.core.film import MAX_RESULTS, get_film_type
from app.core.schemas.query import SearchFilmQuery
from app.utils.url import url_safe_str

# Configure the Jinja2 environment to render HTMl templates
templates = Jinja2Templates(directory=TEMPLATE_DIR)


class NoDocumentationRoute(APIRoute):
    """Exclude routes from OpenAPI documentation.

    Args:
        APIRoute (_type_): _description_
    """

    def __init__(self, path: str, endpoint: Callable, **kwargs):
        kwargs["include_in_schema"] = False
        super().__init__(path, endpoint, **kwargs)


website = APIRouter(
    prefix="",
    tags=["website"],
    route_class=NoDocumentationRoute,
    # responses={404: {"description": "Not found"}},
)


@website.get("/favicon.ico")
async def favicon():
    file_name = "favicon.ico"
    file_path = os.path.join(STATIC_DIR, file_name)
    return FileResponse(path=file_path, headers={"Content-Disposition": "attachment; filename=" + file_name})


@website.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    # Get a random film to populate the home page
    random_id = random.randrange(0, total_count, 1)
    result = film.get_by_id(random_id)

    return templates.TemplateResponse(
        name="index.html",
        context={"request": request, "film": result, "url_safe_str": url_safe_str, "total_count": total_count},
    )


@website.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    return templates.TemplateResponse(name="help.html", context={"request": request})


@website.get("/search", response_class=HTMLResponse)
async def search(request: Request, query: Annotated[SearchFilmQuery, Depends(SearchFilmQuery)]):
    film_type = None

    if query.dx_extract or query.dx_full:
        dx_extract = query.dx_extract or query.dx_full[1:5]
        film_type = get_film_type(dx_extract)
    try:
        films = film.search(
            dx_extract=query.dx_extract,
            dx_full=query.dx_full,
            name=query.name,
            manufacturer=query.manufacturer,
            limit=query.limit,
        )
    except ValueError:
        return RedirectResponse(url="/")
    count = len(films)
    too_many_results = False
    if count >= MAX_RESULTS:
        too_many_results = True

    return templates.TemplateResponse(
        name="search.html",
        context={
            "request": request,
            "count": count,
            "films": films,
            "url_safe_str": url_safe_str,
            "film_type": film_type,
            "too_many_results": too_many_results,
        },
    )


@website.get("/film/{url_name}", response_class=HTMLResponse)
async def read_film(
    request: Request, url_name: Annotated[str, Path(description="Unique URL-safe name of the film", max_length=255)]
):
    result = film.get_by_url(url_name)
    film_type = get_film_type(result.dx_extract) if result and result.dx_extract else None

    return templates.TemplateResponse(
        name="film.html", context={"request": request, "film": result, "film_type": film_type}
    )
