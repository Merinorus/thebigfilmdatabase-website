import sqlite3

import httpx
import pytest
from fastapi import FastAPI

from app.api.routes import api
from app.core import film
from app.utils.sql import combined_search_param


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

        def insert(name, manufacturer=None, notes=None, distributor=None, country=None, dx=None):
            db.execute(
                "INSERT INTO films (name, url_name, manufacturer, og_film_or_information, distributor, country, dx_extract) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [name, name.lower().replace(" ", "-"), manufacturer, notes, distributor, country, dx],
            )

        yield insert
    finally:
        db.close()


def test_group_priority_before_limit(add_film):
    # More than the old 101-row cutoff, alphabetically ahead of the direct matches.
    for i in range(110):
        add_film(f"A Notes {i}", notes="Kodak Gold")
    add_film("B Gold", manufacturer="Kodak")
    add_film("C Gold", distributor="Kodak")
    add_film("Z Kodak Gold")
    add_film("D Gold", country="Kodak")
    add_film("E Kodak")
    results = film.search(q="kodak gold", limit=4)
    assert results[0].name == "Z Kodak Gold"
    assert {result.name for result in results[1:3]} == {"B Gold", "C Gold"}
    assert results[3].name.startswith("A Notes")


def test_prefix_only_on_last_word(add_film):
    add_film("Kodak Gold")
    assert len(film.search(q="kodak gol")) == 1
    assert film.search(q="koda gold") == []


def test_literal_terms_and_empty_input(add_film):
    add_film("Kodak Gold")
    assert combined_search_param('kodak + "gold"*') == '"kodak" AND "gold"*'
    assert len(film.search(q='kodak + "gold"*')) == 1
    assert film.search(q="kodak OR gold") == []
    assert film.search(q="--- : *") == []
    add_film("ФоМос Élite")
    assert len(film.search(q="фомос elite")) == 1


@pytest.mark.anyio
async def test_api_filters_and_validation(add_film, api_app):
    add_film("Kodak Gold", manufacturer="Kodak", dx="1251")
    add_film("Other Gold", manufacturer="Fuji", notes="Kodak", dx="1252")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url="http://test") as client:
        response = await client.get(
            "/api/search", params={"q": "kodak gold", "manufacturer": "kodak", "name": "gold", "dx_extract": "1251"}
        )
        assert response.status_code == 200
        assert [item["name"] for item in response.json()["data"]] == ["Kodak Gold"]
        response = await client.get("/api/search", params={"q": "gold", "dx_extract": "1253"})
        assert response.json()["data"] == []
        response = await client.get("/api/search", params={"name": "gold", "manufacturer": "fuji"})
        assert [item["name"] for item in response.json()["data"]] == ["Other Gold"]
        response = await client.get("/api/search", params={"q": "x" * 256})
        assert response.status_code == 422
        response = await client.get("/api/search", params={"q": "---"})
        assert response.json()["data"] == []
