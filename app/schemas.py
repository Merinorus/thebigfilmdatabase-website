"""Pydantic validation schemas"""

from enum import IntEnum
from typing import Any
from urllib.parse import urljoin

from pydantic import BaseModel, Field, GetCoreSchemaHandler, field_validator, model_validator
from pydantic_core import CoreSchema, core_schema

from app.config import settings

image_cdn_base_url = settings.IMAGE_CDN_BASE_URLS[0]


class DxCode(str):
    """A 4-digit DX Film code"""

    LENGTH = 4

    @classmethod
    def parse_dx_code(cls, v: Any, info: core_schema.ValidationInfo) -> Any:
        """
        Cast the value to a string, ensure it's like an integer and limit the number of digits.

        If empty string, return None.
        """
        if v is None or len(v) == 0:
            return None
        v = str(int(str(v).strip()))
        if len(v) > cls.LENGTH:
            raise ValueError(f"Length should be lower or equal than {cls.LENGTH}")
        return v

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.chain_schema(
            [
                core_schema.with_info_plain_validator_function(
                    function=cls.parse_dx_code,
                ),
            ]
        )


class DxFull(DxCode):
    """A 6-digit DX Film code"""

    LENGTH = 6


class AvailabilityStatus(IntEnum):
    DISCONTINUED = 0
    UNKNOWN = 1
    ON_THE_MARKET = 2
    ON_THE_MARKET_BIS = 3


class FilmInDB(BaseModel):
    dx_extract: str | None = None
    dx_full: str | None = None
    name: str = Field(max_length=255)
    url_name: str = Field(max_length=255)
    original_film_or_information: str | None = None
    manufacturer: str | None = None
    country: str | None = None
    begin_year: str | None = None
    end_year: str | None = None
    distributor: str | None = None
    availability: AvailabilityStatus | None = None
    picture: str | None = None

    # @model_validator(mode="after")
    # def check_dx_code_match_dx_full(self) -> Self:
    #     if self.dx_extract and self.dx_full:
    #         if self.dx_extract != self.dx_full[1:5]:
    #             raise ValueError(f"DX full code ({self.dx_full}) doesn't match the DX extract ({self.dx_extract}). One of the two values is incorrect.")
    #     return self

    @property
    def dx_extract_full_mismatch(self) -> bool:
        """
        Return True if both DX Extract and DX full are set, but don't match.

        This means that either one or the other is not set properly.
        """
        return self.dx_extract and self.dx_full and self.dx_extract != self.dx_full[1:5]

    @field_validator("picture", mode="after")
    def absolute_picture_url(cls, value):
        if value:
            value = str(urljoin(str(image_cdn_base_url), value))
        return value


class HTMLFilmInDB(FilmInDB):
    availability_label: str | None = None

    @model_validator(mode="before")
    @classmethod
    def set_availability_label(cls, values):
        availability = values.get("availability")
        if availability == AvailabilityStatus.DISCONTINUED:
            values["availability_label"] = "discontinued :("
        elif availability in (AvailabilityStatus.ON_THE_MARKET, AvailabilityStatus.ON_THE_MARKET_BIS):
            values["availability_label"] = "on the market"
        else:
            values["availability_label"] = "unknown"
        return values

    #     <p><strong>Original Film or information :</strong> {{ film['or_film_or_information'] }}</p>
    # <p><strong>Manufacturer :</strong> {{ film['manufacturer'] }}</p>
    # <p><strong>Country :</strong> {{ film['country'] }}</p>
    # <p><strong>Beginning year :</strong> {{ film['begin_year'] }}</p>
    # <p><strong>End year :</strong> {{ film['end_year'] }}</p>
    # <p><strong>Distributor :</strong> {{ film['distributor'] }}</p>
    # <p><strong>Availability :</strong> {{ film['availability'] }}</p>
    # <p><strong>Picture :</strong> {{ film['picture'] }}</p>
