import sqlite3

import pytest
from fastapi import FastAPI

from app.api.routes import api
from app.core import film


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def api_app():
    app = FastAPI()
    app.include_router(api)
    return app


@pytest.fixture
def add_film(monkeypatch):
    db = sqlite3.connect(":memory:")
    try:
        db.execute(
            "CREATE VIRTUAL TABLE films USING fts5("
            "dx_extract, dx_full, name, og_film_or_information, manufacturer, reliability, "
            "country, begin_year, end_year, distributor, availability, picture, url_name)"
        )
        monkeypatch.setattr(film, "cursor", db.cursor())
        monkeypatch.setattr(film, "db_ram_connection", db)
        film._autocomplete_cached.cache_clear()

        def insert(name, manufacturer=None, notes=None, distributor=None, country=None, dx=None):
            db.execute(
                "INSERT INTO films (name, url_name, manufacturer, og_film_or_information, distributor, country, dx_extract) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [name, name.lower().replace(" ", "-"), manufacturer, notes, distributor, country, dx],
            )

        yield insert
    finally:
        film._autocomplete_cached.cache_clear()
        db.close()
