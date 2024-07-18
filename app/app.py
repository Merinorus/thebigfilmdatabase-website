import os
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Path, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import (
    BaseModel,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.constants import STATIC_DIR, TEMPLATE_DIR
from app.schemas.film import HTMLFilmInDB
from app.schemas.response import BaseResponse
from app.utils.dx import parse_dx_code, two_parts_dx_number_to_dx_extract
from app.utils.sql import sanitize_fulltext_string
from app.utils.url import url_safe_str

app = FastAPI()

# Cache the database in RAM for faster access
db_file_connection = sqlite3.connect(settings.DB_SQLITE_FILEPATH)
db_ram_connection = sqlite3.connect(":memory:")
db_file_connection.backup(db_ram_connection)
db_file_connection.close()

total_count = len(db_ram_connection.cursor().execute("SELECT * FROM films").fetchall())

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configure the Jinja2 environment to render HTMl templates
templates = Jinja2Templates(directory=TEMPLATE_DIR)


# Max results allowed for a search request
MAX_RESULTS = 100


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


@app.get("/health")
async def healthcheck():
    return BaseResponse()


@app.get("/favicon.ico")
async def favicon():
    file_name = "favicon.ico"
    file_path = os.path.join(STATIC_DIR, file_name)
    return FileResponse(path=file_path, headers={"Content-Disposition": "attachment; filename=" + file_name})


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    # Query a random film
    cursor = db_ram_connection.cursor()
    random_id = random.randrange(0, total_count, 1)
    query = "SELECT * FROM films WHERE rowid = ?"
    cursor.execute(query, [random_id])
    row = cursor.fetchone()
    column_names = [description[0] for description in cursor.description]
    film = dict(zip(column_names, row, strict=False))

    return templates.TemplateResponse(
        name="index.html",
        context={"request": request, "film": film, "url_safe_str": url_safe_str, "total_count": total_count},
    )


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    return templates.TemplateResponse(name="help.html", context={"request": request})


def get_film_type(dx_extract: int) -> str | None:
    dx_extract = int(dx_extract)
    cursor = db_ram_connection.cursor()
    row = cursor.execute(
        "SELECT label FROM film_types WHERE ? >= dx_min and ? <= dx_max ORDER BY rowid DESC LIMIT 1",
        [dx_extract, dx_extract],
    ).fetchone()
    column_names = [description[0] for description in cursor.description]
    film_type = dict(zip(column_names, row, strict=False)).get("label") if row else None
    return film_type


class SearchFilmQuery(BaseModel):
    # Add some room space in case client provide unnecessary spaces or half frame number (eg: "162-16/21A")
    # The additional data will be stripped anyway
    dx_number: str | None = Field(max_length=10, default=None)  # Eg: "162-16"

    dx_extract: str | None = Field(max_length=4, default=None)  # Eg: "2594"
    dx_full: str | None = Field(max_length=6, default=None)  # Eg: "025943"
    name: str | None = Field(max_length=255, default=None)
    manufacturer: str | None = Field(max_length=255, default=None)

    @model_validator(mode="before")
    @classmethod
    def strip_and_empty_str_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    v = v.strip()
                    data[k] = v
                if v == "":
                    v = None
                    data[k] = v
        return data

    @field_validator("dx_extract")
    @classmethod
    def dx_code_length(cls, value: Any):
        return parse_dx_code(value, 4)

    @field_validator("dx_full")
    @classmethod
    def dx_full_length(cls, value: str):
        return parse_dx_code(value, 6)

    @model_validator(mode="after")
    def no_both_dx_extract_and_dx_number_parts(self):
        if self.dx_extract and self.dx_number:
            raise ValueError('Either provide the DX extract (4 digits) or provide the DX number ("XXX-XX"). Not both.')
        return self

    @model_validator(mode="after")
    def set_dx_extract_from_dx_parts(self):
        if not self.dx_extract and self.dx_number:
            self.dx_extract = two_parts_dx_number_to_dx_extract(self.dx_number)
        return self


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, query: Annotated[SearchFilmQuery, Depends(SearchFilmQuery)]):
    db_query = "SELECT * FROM films WHERE 1=1"
    params = []
    film_type = None
    dx_extract = None

    if query.dx_extract:
        dx_extract = query.dx_extract.zfill(4)
        db_query += " AND dx_extract = ?"
        params.append(dx_extract)
    if query.dx_full:
        # Remove the 1st digit as it the same sort of film
        # Remove also the 6th digit as it only means the number of half frame. Sort later
        # Sort the results after DB query
        dx_full = query.dx_full.zfill(6)
        # Keep the part "OR dx_full = ?" because some films still have mismatching dx_part and dx_full numbers.
        db_query += " AND (dx_extract = ? AND dx_full LIKE ? OR dx_full = ?)"
        dx_extract = query.dx_extract or dx_full[1:5]
        dx_full_cropped = dx_full[1:5]
        params.extend([dx_extract, f"_{dx_full_cropped}_", dx_full])
    if dx_extract:
        # Retrieve the film type if the dx_code or the dx_full has been provided
        film_type = get_film_type(dx_extract)
    if query.name:
        db_query += " AND name MATCH ?"
        params.append(f'"{sanitize_fulltext_string(query.name)}*"')
    if query.manufacturer:
        db_query += " AND manufacturer MATCH ?"
        params.append(f'"{sanitize_fulltext_string(query.manufacturer)}*"')
    if params:
        order_by_params = []
        if query.dx_extract or query.dx_full:
            order_by_params.append("case when dx_full is null then 1 else 0 end, dx_full, dx_extract")
        if query.manufacturer:
            order_by_params.append("manufacturer")
        order_by_params.append("name, rowid")
        db_query += " ORDER BY " + ", ".join(order_by_params) + " LIMIT ?"
        params.append(MAX_RESULTS)
        cursor = db_ram_connection.cursor()
        try:
            cursor.execute(db_query, params)
            rows = cursor.fetchall()

            # Convert rows to dictionary
            column_names = [description[0] for description in cursor.description]
            films = [dict(zip(column_names, row, strict=False)) for row in rows]
        except sqlite3.OperationalError as e:
            print(f"SQL Error detected: query will silently fail and return no result. Error detail:\n{e}")
            films = []

    else:
        redirect_url = request.url_for("index_page")
        return RedirectResponse(redirect_url)

    ta = TypeAdapter(list[HTMLFilmInDB])
    models = ta.validate_python(films)

    # Intelligent sort by name if only this has been provided
    if query.name and not any([query.dx_extract, query.dx_full, query.manufacturer]):
        # contains the exact provided name, ignoring the special characters
        models.sort(
            key=lambda x: sanitize_fulltext_string(query.name) in sanitize_fulltext_string(x.name), reverse=True
        )
        # starts with the provided name, ignoring the special characters
        models.sort(
            key=lambda x: sanitize_fulltext_string(x.name).startswith(sanitize_fulltext_string(query.name)),
            reverse=True,
        )
        # contains the exact provided name
        models.sort(key=lambda x: query.name.lower() in str(x.name).lower(), reverse=True)
        # starts with the exact provided name
        models.sort(key=lambda x: str(x.name).startswith(query.name), reverse=True)
        # is exactly the provided name
        models.sort(key=lambda x: str(x.name).lower() == query.name.lower(), reverse=True)

    # If a DX full number is provided and matches several films (eg: 012514 -> 012514, 012513, 912513)
    if query.dx_full:
        # is the provided DX Full number, except the last digit (number of full-frame exposures)
        models.sort(key=lambda x: x.dx_full.startswith(query.dx_full[:-1]), reverse=True)
        # is exactly the provided DX Full number
        models.sort(key=lambda x: x.dx_full == query.dx_full, reverse=True)

    films = [model.model_dump(exclude_none=True) for model in models]
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


@app.get("/film/{url_name}", response_class=HTMLResponse)
async def read_film(
    request: Request, url_name: Annotated[str, Path(description="Unique URL-safe name of the film", max_length=255)]
):
    if url_name != url_safe_str(url_name):
        # Silently refuse unsafe URLs (404 error). All films in DB have a valid url safe name.
        film = None
        film_model = None
    else:
        cursor = db_ram_connection.cursor()
        db_query = "SELECT * FROM films WHERE url_name = ?"
        cursor.execute(db_query, [url_name])
        row = cursor.fetchone()
        column_names = [description[0] for description in cursor.description]
        film_model = HTMLFilmInDB(**dict(zip(column_names, row, strict=False))) if row else None

    film = film_model.model_dump(exclude_none=True) if film_model else None
    film_type = get_film_type(film_model.dx_extract) if film_model and film_model.dx_extract else None

    return templates.TemplateResponse(
        name="film.html", context={"request": request, "film": film, "film_type": film_type}
    )
