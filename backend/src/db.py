"""Database connection utilities."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from pymongo import MongoClient

from .config import get_mongo_uri


@lru_cache(maxsize=1)
def _get_client() -> MongoClient:
    """Create (or reuse) a MongoDB client using the configured URI."""

    return MongoClient(get_mongo_uri())


def get_database():
    """Return the application's MongoDB database instance."""

    return _get_client()["university"]


def get_students_collection():
    """Return the collection that stores student documents."""

    return get_database()["students"]


def serialize_student(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a MongoDB student document into a JSON-serialisable dict."""

    student = {
        "_id": str(document.get("_id", "")),
        "full_name": document.get("full_name"),
        "email": document.get("email"),
        "major_dept_id": document.get("major_dept_id"),
        "year": None,
    }

    year = document.get("year")
    if year is not None:
        student["year"] = str(year)

    if "pronouns" in document:
        student["pronouns"] = document.get("pronouns")
    return student


__all__ = [
    "get_database",
    "get_students_collection",
    "serialize_student",
]
