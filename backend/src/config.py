"""Application configuration helpers."""

import os

from dotenv import load_dotenv

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOTENV_PATH = os.path.join(_BASE_DIR, ".env")

if os.path.exists(_DOTENV_PATH):
    load_dotenv(_DOTENV_PATH)


class ConfigError(RuntimeError):
    """Raised when configuration values are missing or invalid."""


_MONGO_URI_CACHE = None
_DB_NAME_CACHE = None


def get_mongo_uri():
    """Return the MongoDB connection string from the environment."""

    global _MONGO_URI_CACHE

    if _MONGO_URI_CACHE:
        return _MONGO_URI_CACHE

    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise ConfigError("MONGODB_URI is not set. Define it in backend/.env.")

    _MONGO_URI_CACHE = uri
    return uri


def get_db_name():
    """Return the database name derived from the MongoDB URI or env var."""

    global _DB_NAME_CACHE

    if _DB_NAME_CACHE:
        return _DB_NAME_CACHE

    db_name = os.getenv("MONGODB_DB")
    if db_name:
        _DB_NAME_CACHE = db_name
        return db_name

    uri = get_mongo_uri()
    main = uri.split("?", 1)[0].rstrip("/")
    if not main:
        raise ConfigError(
            "Database name not found. Provide it via MONGODB_URI or MONGODB_DB."
        )

    if "://" in main:
        after_scheme = main.split("://", 1)[1]
    else:
        after_scheme = main

    if "/" not in after_scheme:
        raise ConfigError(
            "Database name not found. Provide it via MONGODB_URI or MONGODB_DB."
        )

    candidate = after_scheme.split("/", 1)[1]
    if not candidate:
        raise ConfigError(
            "Database name not found. Provide it via MONGODB_URI or MONGODB_DB."
        )

    _DB_NAME_CACHE = candidate
    return candidate


__all__ = ["ConfigError", "get_mongo_uri", "get_db_name"]
