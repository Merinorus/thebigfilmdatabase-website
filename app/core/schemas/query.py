from collections.abc import Sequence
from typing import Any

from fastapi.exceptions import RequestErrorModel, RequestValidationError
from pydantic import BaseModel, Field, PositiveInt, ValidationError, field_validator, model_validator

from app.core.film import MAX_RESULTS
from app.utils.dx import parse_dx_code, two_parts_dx_number_to_dx_extract


def _normalize_errors(errors: Sequence[Any]) -> list[dict[str, Any]]:
    """Normalize Pydantic errors. Inspired from FastAPI source code (fastapi/routing.py)."""
    use_errors: list[Any] = []
    for error in errors:
        if isinstance(error, Exception):
            new_errors = ValidationError(  # type: ignore[call-arg]
                errors=[error], model=RequestErrorModel
            ).errors()
            use_errors.extend(new_errors)
        elif isinstance(error, list):
            use_errors.extend(_normalize_errors(error))
        else:
            use_errors.append(error)
    return use_errors


class QueryModel(BaseModel):
    """
    Validate client queries.

    A validation error will raise a BadRequest error (HTTP 400).
    """

    def __init__(self, **kwargs):
        try:
            super().__init__(**kwargs)
        except ValidationError as e:
            errors = e.errors()
            for error in errors:
                error["loc"] = ("query",) + error["loc"]
                # Remove the pydantic documentation URL
                error.pop("url")
            raise RequestValidationError(_normalize_errors(errors)) from e


class SearchFilmQuery(QueryModel):
    # Add some room space in case client provide unnecessary spaces or half frame number (eg: "162-16/21A")
    # The additional data will be stripped anyway
    dx_number: str | None = Field(
        max_length=10, default=None, description="DX Number with XXX-YY form", example="115-10"
    )  # Eg: "162-16"

    dx_extract: str | None = Field(max_length=4, default=None)  # Eg: "2594"
    dx_full: str | None = Field(max_length=6, default=None)  # Eg: "025943"
    name: str | None = Field(max_length=255, default=None)
    manufacturer: str | None = Field(max_length=255, default=None)
    limit: PositiveInt = Field(le=MAX_RESULTS, default=100)

    @model_validator(mode="before")
    @classmethod
    def strip_and_empty_str_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    v = v.strip()
                    data[k] = v
                if v == "":
                    v = None
                    data[k] = v
        return data

    @field_validator("dx_extract")
    @classmethod
    def dx_code_length(cls, value: Any):
        return parse_dx_code(value, 4)

    @field_validator("dx_full")
    @classmethod
    def dx_full_length(cls, value: str):
        return parse_dx_code(value, 6)

    @model_validator(mode="after")
    def no_both_dx_extract_and_dx_number_parts(self):
        if self.dx_extract and self.dx_number:
            raise ValueError('Either provide the DX extract (4 digits) or provide the DX number ("XXX-XX"). Not both.')
        return self

    @model_validator(mode="after")
    def set_dx_extract_from_dx_parts(self):
        if not self.dx_extract and self.dx_number:
            self.dx_extract = two_parts_dx_number_to_dx_extract(self.dx_number)
        return self
