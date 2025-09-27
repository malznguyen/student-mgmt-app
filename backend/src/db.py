"""Database connection utilities."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection

from .config import get_db_name, get_mongo_uri


@lru_cache(maxsize=1)
def _get_client() -> MongoClient:
    """Create (or reuse) a MongoDB client using the configured URI."""

    return MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=5000)


@lru_cache(maxsize=1)
def get_db():
    """Return the application's MongoDB database instance."""

    return _get_client()[get_db_name()]


_students_indexes_created = False


def _ensure_students_indexes(collection: Collection) -> None:
    global _students_indexes_created
    if _students_indexes_created:
        return

    collection.create_index("email", unique=True, name="unique_email")
    collection.create_index(
        [("major_dept_id", ASCENDING), ("year", DESCENDING)],
        name="major_year",
        background=True,
    )
    _students_indexes_created = True


def get_students_collection() -> Collection:
    """Return the collection that stores student documents."""

    collection = get_db()["students"]
    _ensure_students_indexes(collection)
    return collection


def serialize_student(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a MongoDB student document into a JSON-serialisable dict."""

    year = document.get("year")
    if isinstance(year, str) and year.isdigit():
        year_value: int | None = int(year)
    elif isinstance(year, (int, float)):
        year_value = int(year)
    else:
        year_value = None

    student = {
        "_id": str(document.get("_id", "")),
        "full_name": document.get("full_name"),
        "email": document.get("email"),
        "major_dept_id": document.get("major_dept_id"),
        "year": year_value,
    }

    if "pronouns" in document:
        student["pronouns"] = document.get("pronouns")
    if "phone" in document:
        student["phone"] = document.get("phone")

    return student


__all__ = [
    "get_db",
    "get_students_collection",
    "serialize_student",
]
