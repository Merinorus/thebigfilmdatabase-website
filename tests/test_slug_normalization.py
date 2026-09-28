import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import api
from app.utils.url import UniqueUrlGenerator, normalize_slug, normalize_unique_slugs, url_safe_str
from app.website.routes import website


def test_slug_generation_and_legacy_suffixes():
    assert url_safe_str("  Kodak — Gold  200 ") == "kodak-gold-200"
    assert normalize_slug("--kodak---gold-200--") == "kodak-gold-200"
    legacy = UniqueUrlGenerator(normalize=False)
    slugs = [legacy.generate(name) for name in ["Kodak — Gold", "Kodak — Gold"]]
    assert normalize_unique_slugs(slugs) == ["kodak-gold", "kodak-gold-1"]
    assert UniqueUrlGenerator().generate("Kodak — Gold") == "kodak-gold"


@pytest.mark.parametrize("slugs", [["a--b", "a-b"], ["a-b-", "a-b"], ["---"]])
def test_normalization_rejects_ambiguous_or_empty_slugs(slugs):
    with pytest.raises(ValueError):
        normalize_unique_slugs(slugs)


@pytest.mark.anyio
@pytest.mark.parametrize("prefix", ["", "/api"])
async def test_canonical_redirects_and_missing_urls(add_film, prefix):
    add_film("Kodak Gold 200")
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(website)
    app.include_router(api)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        canonical = f"{prefix}/film/kodak-gold-200"
        for slug in ["kodak--gold-200", "--kodak---gold-200--", "kodak-gold-200-"]:
            response = await client.get(f"{prefix}/film/{slug}")
            assert response.status_code == 301
            assert response.headers["location"] == canonical
            assert "Cache-Control" in response.headers
            response = await client.get(response.headers["location"])
            assert response.status_code == 200
            assert "location" not in response.headers
            if prefix:
                assert response.json()["data"]["url_name"] == "kodak-gold-200"
        for slug in ["unknown--film-", "kodak--gold-200!", "---"]:
            response = await client.get(f"{prefix}/film/{slug}")
            assert response.status_code == 404
            assert "location" not in response.headers
            if prefix:
                assert response.json()["status"] == "error"
                assert "suggestions" in response.json()["data"]
