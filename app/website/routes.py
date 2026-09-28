import os
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.routing import APIRoute
from fastapi.templating import Jinja2Templates

from app.constants import STATIC_DIR, TEMPLATE_DIR
from app.core import film
from app.core.database import total_count
from app.core.film import get_film_type
from app.core.schemas.query import SearchFilmQuery
from app.utils.url import url_safe_str

# Configure the Jinja2 environment to render HTMl templates
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# Short freshness on HTML pages to absorb traffic spikes via the CDN, with a long stale window for
# instant serving. Kept short (vs the data) because HTML embeds the front-end (asset refs, layout),
# so a short TTL lets front deploys propagate quickly. The "/" home page is left uncached on purpose:
# it shows a random film, so caching it would freeze the draw.
HTML_CACHE_CONTROL = "public, max-age=600, stale-while-revalidate=2592000"


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
    result = film.get_random(limit=1)[0]

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request, "film": result, "url_safe_str": url_safe_str, "total_count": total_count},
    )


@website.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="help.html", context={"request": request}, headers={"Cache-Control": HTML_CACHE_CONTROL}
    )


@website.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    query: Annotated[SearchFilmQuery, Depends(SearchFilmQuery)],
    page: Annotated[int, Query(ge=1)] = 1,
):
    film_type = None

    if query.dx_extract or query.dx_full:
        dx_extract = query.dx_extract or query.dx_full[1:5]
        film_type = get_film_type(dx_extract)
    films, count = film.search_page(
        dx_extract=query.dx_extract,
        dx_full=query.dx_full,
        name=query.name,
        manufacturer=query.manufacturer,
        q=query.q,
        limit=query.limit,
        page=page,
    )
    pages = max(1, (count + query.limit - 1) // query.limit)
    if page > pages:
        raise HTTPException(status_code=404, detail="Page not found")

    # Keep the original filters (including DX number) and encode values safely.
    def page_url(number: int) -> str:
        url = request.url.remove_query_params("page")
        return str(url if number == 1 else url.include_query_params(page=number))

    # Show a stable window of up to ten consecutive pages, including near either end.
    first_page = max(1, min(page - 4, pages - 9))
    page_links = [
        {"number": number, "url": page_url(number)} for number in range(first_page, min(pages, first_page + 9) + 1)
    ]
    is_catalogue = not any((query.dx_extract, query.dx_full, query.name, query.manufacturer, query.q))
    search_terms = []
    if query.q:
        search_terms.append(f"“{query.q}”")
    for label, value in (
        ("Name", query.name),
        ("Manufacturer", query.manufacturer),
        ("DX number", query.dx_number),
        ("DX extract", query.dx_extract if not query.dx_number else None),
        ("DX full", query.dx_full),
    ):
        if value:
            search_terms.append(f"{label}: {value}")
    search_description = "All films" if is_catalogue else "Results for " + " · ".join(search_terms)

    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={
            "request": request,
            "count": count,
            "films": films,
            "url_safe_str": url_safe_str,
            "film_type": film_type,
            "is_catalogue": is_catalogue,
            "search_description": search_description,
            "page": page,
            "pages": pages,
            "page_links": page_links,
            "previous_url": page_url(page - 1) if page > 1 else None,
            "next_url": page_url(page + 1) if page < pages else None,
            "first_result": (page - 1) * query.limit + 1 if count else 0,
            "last_result": (page - 1) * query.limit + len(films),
        },
        headers={"Cache-Control": HTML_CACHE_CONTROL},
    )


@website.get("/film/{url_name}", response_class=HTMLResponse)
async def read_film(
    request: Request, url_name: Annotated[str, Path(description="Unique URL-safe name of the film", max_length=255)]
):
    result = film.get_by_url(url_name)
    if result is not None and url_name != result.url_name:
        return RedirectResponse(
            url=f"/film/{result.url_name}", status_code=301, headers={"Cache-Control": HTML_CACHE_CONTROL}
        )
    suggestions = film.suggest_for_missing_url(url_name) if result is None else []
    film_type = get_film_type(result.dx_extract) if result and result.dx_extract else None

    return templates.TemplateResponse(
        request=request,
        name="film.html",
        context={"request": request, "film": result, "film_type": film_type, "suggestions": suggestions},
        status_code=200 if result is not None else 404,
        headers={"Cache-Control": HTML_CACHE_CONTROL},
    )
