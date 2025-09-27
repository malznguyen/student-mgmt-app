"""Application configuration helpers."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
_DOTENV_PATH = _BASE_DIR / ".env"

if _DOTENV_PATH.exists():
    load_dotenv(_DOTENV_PATH)


class ConfigError(RuntimeError):
    """Raised when configuration values are missing or invalid."""


@lru_cache(maxsize=None)
def get_mongo_uri() -> str:
    """Return the MongoDB connection string from the environment.

    Raises
    ------
    ConfigError
        If the ``MONGODB_URI`` variable is not defined.
    """

    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise ConfigError("MONGODB_URI is not set. Define it in backend/.env.")
    return uri


__all__ = ["ConfigError", "get_mongo_uri"]
