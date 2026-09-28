import httpx
import pytest

from app.core import film
from app.utils.sql import combined_search_param


def test_group_priority_before_limit(add_film):
    # More than the old 101-row cutoff, alphabetically ahead of the direct matches.
    for i in range(110):
        add_film(f"A Notes {i}", notes="Kodak Gold")
    add_film("B Gold", manufacturer="Kodak")
    add_film("C Gold", distributor="Kodak")
    add_film("Z Kodak Gold")
    add_film("D Gold", country="Kodak")
    add_film("E Kodak")
    results = film.search(q="kodak gold", limit=5)
    assert results[0].name == "Z Kodak Gold"
    assert {result.name for result in results[1:3]} == {"B Gold", "C Gold"}
    # The country match now qualifies; its name also contains Gold.
    assert results[3].name == "D Gold"
    assert results[4].name.startswith("A Notes")


def test_prefix_only_on_last_word(add_film):
    add_film("Kodak Gold")
    assert len(film.search(q="kodak gol")) == 1
    assert film.search(q="koda gold") == []


def test_country_matches_with_low_priority_and_pagination(add_film):
    add_film("A Kodak", country="Japan")
    add_film("B Kodak", notes="Japan")
    add_film("C Kodak", distributor="Japan")
    add_film("D Kodak Japan")
    add_film("E Kodak", country="Germany")
    results, total = film.search_page(q="kodak japan", limit=3)
    assert total == 4
    assert [item.name for item in results] == ["D Kodak Japan", "C Kodak", "B Kodak"]
    results, total = film.search_page(q="kodak japan", limit=3, page=2)
    assert total == 4
    assert [item.name for item in results] == ["A Kodak"]
    assert [item.name for item in film.search(q="kodak ger")] == ["E Kodak"]


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
    add_film("Kodak Gold", manufacturer="Kodak", dx="1251", country="Made in Japan ?")
    add_film("Other Gold", manufacturer="Fuji", notes="Kodak", dx="1252")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url="http://test") as client:
        response = await client.get(
            "/api/search", params={"q": "kodak gold", "manufacturer": "kodak", "name": "gold", "dx_extract": "1251"}
        )
        assert response.status_code == 200
        assert [item["name"] for item in response.json()["data"]] == ["Kodak Gold"]
        response = await client.get("/api/search", params={"q": "kodak japan"})
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
