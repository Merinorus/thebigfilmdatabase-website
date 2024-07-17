"""Pydantic validation schemas"""

from enum import IntEnum
from typing import Any, Union
from urllib.parse import urljoin

from pydantic import (
    BaseModel,
    Field,
    GetCoreSchemaHandler,
    NonNegativeInt,
    field_validator,
    model_validator,
)
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

    @classmethod
    def json_format(cls, status: Union["AvailabilityStatus", None]):
        json_formats = {
            AvailabilityStatus.DISCONTINUED: "discontinued",
            AvailabilityStatus.UNKNOWN: "unknown",
            AvailabilityStatus.ON_THE_MARKET: "on_the_market",
            AvailabilityStatus.ON_THE_MARKET_BIS: "on_the_market",
        }
        return json_formats.get(status, "unknown") if status is not None else "unknown"

    @classmethod
    def html_format(cls, status: Union["AvailabilityStatus", None]):
        html_formats = {
            AvailabilityStatus.DISCONTINUED: "<font color=red>discontinued :(</font>",
            AvailabilityStatus.UNKNOWN: "unknown",
            AvailabilityStatus.ON_THE_MARKET: "<font color=green>on the market</font>",
            AvailabilityStatus.ON_THE_MARKET_BIS: "<font color=green>on the market</font>",
        }
        return html_formats.get(status, "unknown") if status is not None else "unknown"


class FilmInDB(BaseModel):
    dx_extract: str | None = None
    dx_full: str | None = None
    name: str = Field(max_length=255)
    url_name: str = Field(max_length=255)
    og_film_or_information: str | None = None
    reliability: NonNegativeInt | None = Field(max=4)
    manufacturer: str | None = None
    manufacturers: list[str] = None
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

    @field_validator("*", mode="before")
    def empty_str_as_none(cls, value):
        if isinstance(value, str) and value == "":
            value = None
        return value

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

    @model_validator(mode="after")
    def fill_manufacturer_list(self):
        if self.manufacturer:
            self.manufacturers = self.manufacturer.split(", ")
        return self


class HTMLFilmInDB(FilmInDB):
    availability_label: str | None = None
    reliability_img: str | None = None

    @model_validator(mode="after")
    def set_availability_label(self):
        self.availability_label = AvailabilityStatus.html_format(self.availability)
        return self

    @model_validator(mode="after")
    def set_reliability_img(self):
        if self.reliability is not None:
            self.reliability_img = f"/static/images/{self.reliability}.gif"
        return self

    # @model_validator(mode="after")
    # def set_reliability_img(self):
    #     if self.reliability is not None:
    #         self.reliability_img = f"{self.reliability}.gif"
    #     return self

    #     <p><strong>Original Film or information :</strong> {{ film['or_film_or_information'] }}</p>
    # <p><strong>Manufacturer :</strong> {{ film['manufacturer'] }}</p>
    # <p><strong>Country :</strong> {{ film['country'] }}</p>
    # <p><strong>Beginning year :</strong> {{ film['begin_year'] }}</p>
    # <p><strong>End year :</strong> {{ film['end_year'] }}</p>
    # <p><strong>Distributor :</strong> {{ film['distributor'] }}</p>
    # <p><strong>Availability :</strong> {{ film['availability'] }}</p>
    # <p><strong>Picture :</strong> {{ film['picture'] }}</p>
