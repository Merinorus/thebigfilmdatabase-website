import random
import sqlite3
from typing import Annotated, Any

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.config import settings
from app.constants import TEMPLATE_DIR
from app.schemas import HTMLFilmInDB
from app.utils.url import url_safe_str

app = FastAPI()

# # Create the SQLite database from the CSV film database
# update_db()

# Cache the database in RAM for faster access
db_file_connection = sqlite3.connect(settings.DB_SQLITE_FILEPATH)
db_ram_connection = sqlite3.connect(":memory:")
db_file_connection.backup(db_ram_connection)
db_file_connection.close()

total_count = len(db_ram_connection.cursor().execute("SELECT * FROM films").fetchall())

# Configure the Jinja2 environment
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)

MAX_RESULTS = 100


class BaseResponse(BaseModel):
    status: str = "ok"


@app.get("/health")
async def healthcheck():
    return BaseResponse()


@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Query a random film
    cursor = db_ram_connection.cursor()
    random_id = random.randrange(0, total_count, 1)
    query = "SELECT * FROM films WHERE rowid = ?"
    cursor.execute(query, [random_id])
    row = cursor.fetchone()
    column_names = [description[0] for description in cursor.description]
    film = dict(zip(column_names, row, strict=False))

    template = env.get_template("index.html")
    return template.render(film=film, url_safe_str=url_safe_str, total_count=total_count)


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


def _empty_str_to_none(v: str | None) -> None:
    if v is None:
        return None
    if isinstance(v) and v.strip() == "":
        return None
    raise ValueError("Value is not empty")  # Not str or None, Fall to next type. e.g. Decimal, or a non-empty str


# EmptyStrToNone: TypeAlias = Annotated[str, StringConstraints(strip_whitespace=True,)]

DxCodeStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=6)]
# Define the Pydantic model for query parameters


def parse_dx_code(dx_code: Any, max_digits=6) -> str | None:
    """Stringify a DX code number if provided. Return a string or None."""
    if not dx_code:
        return None
    result = int(dx_code)
    result = str(result).zfill(max_digits)
    if len(result) > max_digits:
        raise ValueError(f"Length should be lower or equal than {max_digits}")
    return result


class SearchFilmQuery(BaseModel):
    # dx_code: DxCode = Field(None, description="4-digit long DX film code")
    # dx_full: DxFull = Field(None, description="6-digit long full DX film code")

    dx_extract: str | None = Field(max_length=4)
    dx_full: str | None = Field(max_length=6)
    name: str | None = Field(max_length=255)
    manufacturer: str | None = Field(max_length=255)

    # name: Annotated[str, StringConstraints(strip_whitespace=True)] = Field(None, min_length=3, max_length=255, description="Approximate name of the film")
    # manufacturer: Annotated[str, StringConstraints(strip_whitespace=True)] = Field(None, min_length=3, max_length=255, description="Manufacturer name")

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


@app.get("/search", response_class=HTMLResponse)
async def search(query: SearchFilmQuery = Depends()):
    print(query.dx_extract)
    db_query = "SELECT * FROM films WHERE 1=1"
    params = []
    film_type = None
    dx_extract = None
    if not query:
        return read_root()

    if query.dx_extract:
        dx_extract = query.dx_extract.zfill(4)
        db_query += " AND [dx_extract] LIKE ?"
        params.append(f"%{dx_extract}%")
    if query.dx_full:
        dx_full = query.dx_full.zfill(6)
        db_query += " AND [dx_full] LIKE ?"
        params.append(f"%{dx_full}%")
        dx_extract = dx_full[1:5]
    if dx_extract:
        # Retrieve the film type if the dx_code or the dx_full has been provided
        film_type = get_film_type(dx_extract)
    if query.name:
        db_query += " AND name MATCH ?"
        params.append(f"{query.name}*")
    if query.manufacturer:
        db_query += " AND manufacturer LIKE ?"
        params.append(f"%{query.manufacturer}%")
    if params:
        db_query += "LIMIT ?"
        params.append(MAX_RESULTS)
        cursor = db_ram_connection.cursor()
        cursor.execute(db_query, params)
        rows = cursor.fetchall()

        # Convert rows to dictionary
        column_names = [description[0] for description in cursor.description]
        films = [dict(zip(column_names, row, strict=False)) for row in rows]
    else:
        # No filter was provided from the client
        films = []

    ta = TypeAdapter(list[HTMLFilmInDB])
    models = ta.validate_python(films)
    films = [model.model_dump(exclude_none=True) for model in models]
    template = env.get_template("search.html")
    return template.render(films=films, url_safe_str=url_safe_str, film_type=film_type)


class UniqueFilmQuery(BaseModel):
    name: str | None = Field(None, description="Unique URL-safe name of the film", max_length=255)


@app.get("/film/{name}", response_class=HTMLResponse)
async def read_film(query: UniqueFilmQuery = Depends()):
    # film = df[df['url_name'] == url_safe_str(name)].to_dict(orient='records')
    cursor = db_ram_connection.cursor()
    db_query = "SELECT * FROM films WHERE url_name = ?"
    cursor.execute(db_query, [query.name])
    row = cursor.fetchone()
    column_names = [description[0] for description in cursor.description]
    film = HTMLFilmInDB(**dict(zip(column_names, row, strict=False))).model_dump(exclude_none=True) if row else None
    if not film:
        return HTMLResponse("Film not found", status_code=404)

    template = env.get_template("film.html")
    return template.render(film=film)
