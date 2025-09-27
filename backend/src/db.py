from __future__ import annotations

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from .config import settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return a cached MongoDB client instance."""
    global _client
    if _client is None:
        _client = MongoClient(settings.mongodb_uri)
    return _client


def get_database() -> Database:
    """Return the target MongoDB database."""
    return get_client()[settings.mongodb_db_name]


def get_collection(name: str) -> Collection:
    """Return a specific collection from the configured database."""
    return get_database()[name]
