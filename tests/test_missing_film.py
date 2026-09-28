from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import SEARCH_FILM_CACHE_CONTROL
from app.core import film
from app.website.routes import website


def test_fallback_stops_at_first_match(add_film):
    add_film("Kodak Gold 200")
    add_film("Kodak Gold 400")
    results = film.suggest_for_missing_url("kodak-gold-200-old-name")
    assert [result.name for result in results] == ["Kodak Gold 200"]


def test_five_removals_maximum(monkeypatch):
    search = Mock(return_value=[])
    monkeypatch.setattr(film, "search", search)
    assert film.suggest_for_missing_url("kodak-one-two-three-four-five-six") == []
    assert search.call_count == 6
    assert search.call_args.kwargs == {"q": "kodak one", "limit": 10}


@pytest.mark.parametrize(
    "slug",
    ["a-" * 100 + "a", "film-color", "kodak!", "k" * 256, "-".join(f"word{i}" for i in range(13))],
)
def test_unhelpful_or_invalid_urls_do_not_search(monkeypatch, slug):
    search = Mock(return_value=[])
    monkeypatch.setattr(film, "search", search)
    assert film.suggest_for_missing_url(slug) == []
    search.assert_not_called()


def test_repeated_words_and_result_limit(add_film):
    for i in range(20):
        add_film(f"Kodak Gold {i}")
    assert len(film.suggest_for_missing_url("kodak-kodak-gold-gold")) == 10


@pytest.mark.anyio
async def test_missing_page_and_existing_page(add_film, monkeypatch):
    add_film("Kodak Gold 200")
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(website)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/film/kodak-gold-200-old")
        assert response.status_code == 404
        assert "Perhaps you were looking" in response.text
        assert 'href="http://test/film/kodak-gold-200"' in response.text
        response = await client.get("/film/unknownfilm")
        assert response.status_code == 404
        assert "Perhaps you were looking" not in response.text
        fallback = Mock(side_effect=AssertionError("Existing films must not run fallback searches"))
        monkeypatch.setattr(film, "suggest_for_missing_url", fallback)
        response = await client.get("/film/kodak-gold-200")
        assert response.status_code == 200
        fallback.assert_not_called()
        response = await client.get("/film/" + "k" * 256)
        assert response.status_code == 422


@pytest.mark.anyio
async def test_api_missing_film_suggestions(add_film, api_app, monkeypatch):
    add_film("Kodak Gold 200")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url="http://test") as client:
        response = await client.get("/api/film/kodak-gold-200-old")
        assert response.status_code == 404
        assert response.headers["Cache-Control"] == SEARCH_FILM_CACHE_CONTROL
        body = response.json()
        assert body["status"] == "error"
        assert [item["url_name"] for item in body["data"]["suggestions"]] == ["kodak-gold-200"]
        assert body["data"]["suggestions"][0]["name"] == "Kodak Gold 200"
        for slug in ("unknownfilm", "a-" * 100 + "a", "kodak!"):
            response = await client.get(f"/api/film/{slug}")
            assert response.status_code == 404
            assert response.json() == {"status": "error", "data": {"suggestions": []}}
        fallback = Mock(side_effect=AssertionError("Existing films must not run fallback searches"))
        monkeypatch.setattr(film, "suggest_for_missing_url", fallback)
        response = await client.get("/api/film/kodak-gold-200")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["data"]["url_name"] == "kodak-gold-200"
        fallback.assert_not_called()
        response = await client.get("/api/film/" + "k" * 256)
        assert response.status_code == 422


def test_api_documents_missing_film_response(api_app):
    schema = api_app.openapi()
    responses = schema["paths"]["/api/film/{url_name}"]["get"]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/FilmResponse")
    assert responses["404"]["content"]["application/json"]["schema"]["$ref"].endswith("/FilmNotFoundResponse")
