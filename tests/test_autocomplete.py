import httpx
import pytest

from app.api.routes import AUTOCOMPLETE_CACHE_CONTROL
from app.core import film


def test_context_can_span_all_identity_columns(add_film):
    """Context and completion can occupy different columns, but must belong to one film."""
    add_film("Gold", manufacturer="Kodak", distributor="Retailer")
    add_film("Gotham", manufacturer="Fuji", notes="Kodak", country="Retailer")
    add_film("Other", manufacturer="Kodak", notes="Gorgeous")

    assert film.autocomplete("search", "kodak retailer go") == ["gold"]
    assert film.autocomplete("search", "gold retailer ko") == ["kodak"]
    assert film.autocomplete("search", "kodak gold re") == ["retailer"]
    # Notes and country neither supply context nor contribute suggestions.
    assert film.autocomplete("search", "kodak go") == ["gold"]
    assert film.autocomplete("search", "fuji retailer go") == []


def test_suggestions_count_films_not_column_occurrences(add_film):
    """Two films containing Portra outrank Gold repeated in three columns of one film."""
    add_film("Kodak Gold", manufacturer="Gold", distributor="Gold")
    add_film("Kodak Portra 100")
    add_film("Kodak Portra 200")
    assert film.autocomplete("search", "kodak ")[:2] == ["portra", "gold"]
    assert film.autocomplete("search", "kodak ", limit=1) == ["portra"]


def test_prefix_next_word_and_stopwords(add_film):
    """Keep the existing short-prefix rules, suppress typed words and demote generic words."""
    add_film("Gold Film", manufacturer="Kodak")
    add_film("Film", manufacturer="Kodak")
    assert film.autocomplete("search", "k") == []
    assert film.autocomplete("search", "ko") == ["kodak"]
    assert film.autocomplete("search", "kodak g") == ["gold"]
    assert film.autocomplete("search", "koda go") == []
    # Gold stays ahead of the more frequent generic word; Kodak is not re-suggested.
    assert film.autocomplete("search", "kodak ") == ["gold", "film"]


def test_literal_input_and_cache_isolation(add_film):
    """Treat operators as literal words and isolate cached results by scope and limit."""
    add_film("Gold", manufacturer="Kodak")
    assert film.autocomplete("search", "kodak + go") == ["gold"]
    assert film.autocomplete("search", "kodak OR go") == []
    assert film.autocomplete("search", "---") == []
    assert film.autocomplete("search", "") == []
    assert film.autocomplete("name", "kodak go") == []
    suggestions = film.autocomplete("search", "kodak go")
    suggestions.append("fake")
    assert film.autocomplete("search", "kodak go") == ["gold"]


@pytest.mark.anyio
async def test_api_combined_and_existing_routes(add_film, api_app):
    """Expose the combined scope with cache headers and validation, keeping old routes scoped."""
    add_film("Gold", manufacturer="Kodak", distributor="Retailer")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url="http://test") as client:
        response = await client.get("/api/autocomplete", params={"q": "kodak go", "limit": 1})
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "data": ["gold"]}
        assert response.headers["cache-control"] == AUTOCOMPLETE_CACHE_CONTROL
        for route, query, expected in [
            ("name", "kodak go", []),
            ("name", "go", ["gold"]),
            ("manufacturer", "ko", ["kodak"]),
            ("manufacturer", "re", []),
        ]:
            response = await client.get(f"/api/autocomplete/{route}", params={"q": query})
            assert response.status_code == 200
            assert response.json()["data"] == expected
        for params in [{}, {"q": "x" * 256}, {"q": "ko", "limit": 0}, {"q": "ko", "limit": 12}]:
            response = await client.get("/api/autocomplete", params=params)
            assert response.status_code == 422
