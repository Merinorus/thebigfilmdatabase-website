from html.parser import HTMLParser
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core import cdn, film
from app.utils.image_path import safe_image_filename
from app.website.routes import website


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.test/a.jpg",
        "//evil.test/a.jpg",
        "javascript:alert(1)",
        "data:image/svg+xml,<svg onload=alert(1)>",
        "../a.jpg",
        "/a.jpg",
        "..\\a.jpg",
        "%2e%2e%2fa.jpg",
        "a.jpg?x=1",
        "a.jpg#x",
        'a" onerror="alert(1).jpg',
        "a\n.jpg",
        "a.svg",
        "a.html",
        "a.jpg\x00",
        "http://127.0.0.1/a.jpg",
    ],
)
def test_untrusted_image_paths_are_rejected(value):
    assert safe_image_filename(value) is None
    assert cdn.get_film_image_url(value) is None
    assert cdn.get_film_image_url(value, cdn_enable=False) is None


def test_image_filename_is_encoded_under_trusted_base():
    assert (
        cdn.get_film_image_url("Film (B&W).jpg", base_url="https://cdn.test/Images/")
        == "https://cdn.test/Images/Film%20%28B%26W%29.jpg"
    )


@pytest.mark.anyio
async def test_cdn_probe_never_requests_untrusted_picture(add_film, monkeypatch):
    add_film("Film")
    film.cursor.execute("UPDATE films SET picture = 'http://127.0.0.1/private.jpg'")
    from app.core import database

    monkeypatch.setattr(database, "db_ram_connection", film.db_ram_connection)
    request = AsyncMock(side_effect=AssertionError("Untrusted image must not be fetched"))
    monkeypatch.setattr(httpx.AsyncClient, "get", request)
    await cdn.update_cdn_url()
    request.assert_not_called()


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/film/film", "/search"])
async def test_templates_escape_even_unsanitized_database_text(add_film, path):
    add_film("Film")
    payload = '<script>alert(1)</script><img src=x onerror="alert(1)"><svg onload="alert(1)">'
    film.cursor.execute(
        "UPDATE films SET name=?, og_film_or_information=?, manufacturer=?, country=?, distributor=?, begin_year=?, end_year=?, picture=?",
        [payload] * 7 + ["javascript:alert(1)"],
    )
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(website)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text
    elements = Elements()
    elements.feed(response.text)
    for tag, attrs in elements.elements:
        assert tag not in {"script", "svg"}
        assert not any(key.startswith("on") for key in attrs)
        assert not attrs.get("src", "").startswith("javascript:")
