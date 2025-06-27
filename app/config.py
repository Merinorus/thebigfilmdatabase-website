"""
Application settings.

All settings can be overridden by a .env file at runtime.
"""

import os

from pydantic import Field, HttpUrl, NonNegativeFloat, NonNegativeInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import PROJECT_DIR

# Provide CDN base URLs that can serve images from the Open source film database Github repository.
_DEFAULT_CDN_BASE_URLS = [
    "https://cdn.jsdelivr.net/gh/merinorus/Open-source-film-database@main/Images/",
    "https://cdn.statically.io/gh/merinorus/Open-source-film-database/main/Images/",
    "https://rawcdn.githack.com/Merinorus/Open-source-film-database/main/Images/",
]


class Settings(BaseSettings):
    DATA_DIR: str = str(os.path.join(PROJECT_DIR, "data"))

    # Location of the open source film database repo.
    # Clone this repo (or a fork) to a local directory: git clone https://github.com/dxdatabase/Open-source-film-database Open-source-film-database
    FILM_DATABASE_REPO_DIR: str = str(os.path.join(PROJECT_DIR, "Open-source-film-database"))

    FILM_IMAGE_DIR: str = str(os.path.join(FILM_DATABASE_REPO_DIR, "Images"))
    FILM_IMAGE_CDN_ENABLE: bool = True
    FILM_IMAGE_CDN_BASE_URLS: list[HttpUrl] = Field(min_length=1, default=_DEFAULT_CDN_BASE_URLS)

    # Location of the local database, created at application launch from the repo's data
    DB_SQLITE_FILEPATH: str = str(os.path.join(DATA_DIR, "film_database.db"))

    RATE_LIMITER_MAX_REQUESTS: NonNegativeInt = Field(default=30)
    RATE_LIMITER_TIME_WINDOW: NonNegativeFloat = Field(default=30)

    model_config = SettingsConfigDict(extra="ignore", env_file=".env", case_sensitive=True)


settings = Settings()
