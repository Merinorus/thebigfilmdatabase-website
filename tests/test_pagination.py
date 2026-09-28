from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.constants import STATIC_DIR
from app.core import film
from app.website.routes import website


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


@pytest.fixture
def website_app():
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(website)
    return app


@pytest.mark.anyio
async def test_catalogue_can_be_crawled_without_javascript(add_film, website_app):
    for i in reversed(range(205)):
        add_film(f"Film {i:03}")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=website_app), base_url="http://test") as client:
        home = await client.get("/")
        assert "action='http://test/search'" in home.text
        url = "/search"
        names = []
        for page in range(1, 4):
            response = await client.get(url)
            assert response.status_code == 200
            assert "Found 205 films." in response.text
            assert f"Page {page} of 3" in response.text
            links = Links(response.text).links
            names.extend(urlsplit(link["href"]).path for link in links if "/film/" in link["href"])
            next_links = [link["href"] for link in links if link.get("rel") == "next"]
            if page < 3:
                url = next_links[0]
            else:
                assert next_links == []
        assert names == [f"/film/film-{i:03}" for i in range(205)]
        assert (await client.get("/search?page=4")).status_code == 404
        assert (await client.get("/search?page=0")).status_code == 422
        assert (await client.get("/search?page=bad")).status_code == 422
        assert (await client.get("/search?page=99999999999999999999999999999")).status_code == 404


@pytest.mark.anyio
async def test_page_links_preserve_encoded_filters(add_film, website_app):
    for i in range(3):
        add_film(f"Kodak Gold {i}", manufacturer="Kodak", dx="1251")
    add_film("Kodak Gold Other", manufacturer="Other", dx="1251")
    filters = {"q": 'kodak + "gold"', "manufacturer": "kodak", "dx_number": "078-03", "limit": "2"}
    film.db_ram_connection.execute("CREATE TABLE film_types (dx_min, dx_max, label)")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=website_app), base_url="http://test") as client:
        response = await client.get("/search", params=filters)
        assert response.status_code == 200
        assert "Found 3 films." in response.text
        next_url = next(link["href"] for link in Links(response.text).links if link.get("rel") == "next")
        assert parse_qs(urlsplit(next_url).query) == {key: [value] for key, value in {**filters, "page": "2"}.items()}
        response = await client.get(next_url)
        assert "Showing 3–3." in response.text
        previous_url = next(link["href"] for link in Links(response.text).links if link.get("rel") == "prev")
        assert "page" not in parse_qs(urlsplit(previous_url).query)


@pytest.mark.anyio
async def test_empty_results_and_single_page(add_film, website_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=website_app), base_url="http://test") as client:
        response = await client.get("/search")
        assert response.status_code == 200
        assert "Found 0 films." in response.text
        assert "No results found" in response.text
        assert 'aria-label="Results pages"' not in response.text
        add_film("Kodak Gold")
        response = await client.get("/search")
        assert "Showing 1–1." in response.text
        assert 'rel="next"' not in response.text
        response = await client.get("/search?q=---")
        assert "Found 0 films." in response.text
        assert (await client.get("/search?q=missing&page=2")).status_code == 404


@pytest.mark.parametrize(
    "filters", [{"q": "gold"}, {"name": "gold"}, {"manufacturer": "kodak"}, {"dx_extract": "1251"}]
)
def test_filtered_results_beyond_old_cap(add_film, filters):
    for i in range(115):
        add_film(f"Gold {i:03}", manufacturer="Kodak", dx="1251")
    first, total = film.search_page(**filters, limit=100)
    second, second_total = film.search_page(**filters, limit=100, page=2)
    assert total == second_total == 115
    assert len(first) == 100
    assert len(second) == 15
    assert len({item.url_name for item in first + second}) == 115


def test_name_ranking_precedes_pagination(add_film):
    for i in range(110):
        add_film(f"A Gold {i:03}")
    add_film("Gold")
    first, total = film.search_page(name="gold", limit=1)
    second, _ = film.search_page(name="gold", limit=1, page=2)
    assert total == 111
    assert first[0].name == "Gold"
    assert second[0].name == "A Gold 000"


def test_dx_ranking_precedes_pagination(add_film):
    for i in range(110):
        add_film(f"A Film {i:03}", dx="1251")
    film.db_ram_connection.execute("UPDATE films SET dx_full = '012513'")
    add_film("Z Exact", dx="1251")
    film.db_ram_connection.execute("UPDATE films SET dx_full = '912514' WHERE name = 'Z Exact'")
    first, total = film.search_page(dx_full="912514", limit=1)
    second, _ = film.search_page(dx_full="912514", limit=1, page=2)
    assert total == 111
    assert first[0].name == "Z Exact"
    assert second[0].name == "A Film 000"


@pytest.mark.anyio
@pytest.mark.parametrize("filtered", [False, True])
async def test_api_pagination(add_film, api_app, filtered):
    for i in reversed(range(115)):
        add_film(f"Gold {i:03}", manufacturer="Kodak", dx="1251")
    filters = {}
    if filtered:
        add_film("Other Gold", manufacturer="Fuji", dx="1251")
        add_film("Other Gold", manufacturer="Kodak", dx="1252")
        filters = {"q": "gold", "manufacturer": "kodak", "dx_number": "078-03"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url="http://test") as client:
        names = []
        for page, size in [(1, 50), (2, 50), (3, 15)]:
            response = await client.get("/api/search", params={**filters, "page": page, "limit": 50})
            assert response.status_code == 200
            payload = response.json()
            assert {key: value for key, value in payload.items() if key != "data"} == {
                "status": "ok",
                "page": page,
                "limit": 50,
                "total": 115,
                "pages": 3,
            }
            assert len(payload["data"]) == size
            names.extend(item["name"] for item in payload["data"])
            assert "max-age=600" in response.headers["Cache-Control"]
        assert names == [f"Gold {i:03}" for i in range(115)]
        response = await client.get("/api/search", params=filters)
        assert response.json()["page"] == 1
        assert response.json()["limit"] == 100
        assert response.json()["pages"] == 2
        assert len(response.json()["data"]) == 100
        response = await client.get("/api/search", params={**filters, "page": 4, "limit": 50})
        assert response.status_code == 404


@pytest.mark.anyio
async def test_api_pagination_empty_and_invalid_pages(add_film, api_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url="http://test") as client:
        response = await client.get("/api/search")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "data": [], "page": 1, "limit": 100, "total": 0, "pages": 1}
        assert (await client.get("/api/search?page=2")).status_code == 404
        add_film("Kodak Gold")
        response = await client.get("/api/search?q=missing")
        assert response.json()["total"] == 0
        assert response.json()["data"] == []
        for query in ("page=0", "page=-1", "page=abc", "page=1.5", "limit=0", "limit=102"):
            assert (await client.get(f"/api/search?{query}")).status_code == 422
        assert (await client.get("/api/search?page=99999999999999999999999999999")).status_code == 404


def test_api_pagination_documented(api_app):
    schema = api_app.openapi()
    search = schema["paths"]["/api/search"]["get"]
    page = next(param for param in search["parameters"] if param["name"] == "page")
    assert page["schema"]["default"] == 1
    assert page["schema"]["minimum"] == 1
    response = search["responses"]["200"]["content"]["application/json"]["schema"]
    assert response["$ref"].endswith("/PaginatedFilmListResponse")
    assert {"data", "page", "limit", "total", "pages"} <= schema["components"]["schemas"]["PaginatedFilmListResponse"][
        "properties"
    ].keys()
