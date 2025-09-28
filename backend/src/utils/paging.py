"""Utilities for parsing pagination and sorting query parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from pymongo import ASCENDING, DESCENDING


class PagingParamError(ValueError):
    """Raised when pagination or sort query parameters are invalid."""


@dataclass
class PagingParams:
    page: int
    page_size: int
    sort: Tuple[str, int]
    normalized_sort: str


def _parse_int_arg(
    raw_value: str | None,
    *,
    name: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if raw_value in (None, ""):
        value = default
    else:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            raise PagingParamError(f"{name} must be an integer.") from None

    if minimum is not None and value < minimum:
        raise PagingParamError(f"{name} must be ≥ {minimum}.")
    if maximum is not None and value > maximum:
        raise PagingParamError(f"{name} must be ≤ {maximum}.")

    return value


def _parse_sort_arg(
    raw_sort: str | None,
    *,
    allowed_fields: Mapping[str, str],
    default_sort: str,
) -> Tuple[Tuple[str, int], str]:
    if not allowed_fields:
        raise PagingParamError("No sort fields configured.")

    sort_value = raw_sort or default_sort
    direction = ASCENDING
    field_key = sort_value

    if sort_value.startswith("-"):
        direction = DESCENDING
        field_key = sort_value[1:]

    if field_key not in allowed_fields:
        field_names = sorted(allowed_fields.keys())
        options = [
            value
            for field in field_names
            for value in (field, f"-{field}")
        ]
        raise PagingParamError(
            "sort must be one of: " + ", ".join(options) + "."
        )

    return (allowed_fields[field_key], direction), (
        f"-{field_key}" if direction == DESCENDING else field_key
    )


def parse_paging_params(
    args: Mapping[str, str],
    *,
    default_page: int = 1,
    default_page_size: int = 10,
    max_page_size: int = 100,
    allowed_sort_fields: Mapping[str, str],
    default_sort: str,
) -> PagingParams:
    """Parse standard pagination parameters from a request args mapping."""

    page = _parse_int_arg(
        args.get("page"),
        name="page",
        default=default_page,
        minimum=1,
    )

    page_size = _parse_int_arg(
        args.get("page_size"),
        name="page_size",
        default=default_page_size,
        minimum=1,
        maximum=max_page_size,
    )

    sort_tuple, normalized_sort = _parse_sort_arg(
        args.get("sort"),
        allowed_fields=allowed_sort_fields,
        default_sort=default_sort,
    )

    return PagingParams(
        page=page,
        page_size=page_size,
        sort=sort_tuple,
        normalized_sort=normalized_sort,
    )

