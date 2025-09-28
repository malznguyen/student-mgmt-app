"""MongoDB helpers for the application."""

from pymongo import ASCENDING, DESCENDING, IndexModel, MongoClient
from pymongo.collection import Collection

from .config import get_db_name, get_mongo_uri

_MONGO_CLIENT = None
_MONGO_DB = None


def _get_client():
    """Create (or reuse) a MongoDB client using the configured URI."""

    global _MONGO_CLIENT

    if _MONGO_CLIENT is None:
        _MONGO_CLIENT = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=5000)
    return _MONGO_CLIENT


def get_db():
    """Return the application's MongoDB database instance."""

    global _MONGO_DB

    if _MONGO_DB is None:
        _MONGO_DB = _get_client()[get_db_name()]
    return _MONGO_DB


_students_indexes_created = False
_courses_indexes_created = False
_sections_indexes_created = False
_enrollments_indexes_created = False


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
    collection.create_index(
        [("full_name", ASCENDING)],
        name="full_name_asc",
        background=True,
    )
    _students_indexes_created = True


def get_students_collection() -> Collection:
    """Return the collection that stores student documents."""

    collection = get_db()["students"]
    _ensure_students_indexes(collection)
    return collection


def serialize_student(document):
    """Convert a MongoDB student document into a JSON-serialisable dict."""

    year = document.get("year")
    if isinstance(year, str) and year.isdigit():
        year_value = int(year)
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


def _ensure_courses_indexes(collection: Collection) -> None:
    global _courses_indexes_created
    if _courses_indexes_created:
        return

    collection.create_indexes(
        [
            IndexModel(
                [("dept_id", ASCENDING)],
                name="dept_id_idx",
                background=True,
            ),
            IndexModel(
                [("title", ASCENDING)],
                name="title_idx",
                background=True,
            ),
        ]
    )
    _courses_indexes_created = True


def get_courses_collection() -> Collection:
    """Return the courses collection and ensure supporting indexes."""

    collection = get_db()["courses"]
    _ensure_courses_indexes(collection)
    return collection


def serialize_course(document):
    """Serialize a raw Mongo course document to JSON-friendly dict."""

    credits = document.get("credits")
    try:
        credits_value = int(credits) if credits is not None else None
    except (TypeError, ValueError):
        credits_value = None

    prereqs = document.get("prereq_ids", [])
    if not isinstance(prereqs, list):
        prereqs = []

    return {
        "_id": str(document.get("_id", "")),
        "title": document.get("title"),
        "dept_id": document.get("dept_id"),
        "credits": credits_value,
        "prereq_ids": prereqs,
    }


def _ensure_sections_indexes(collection: Collection) -> None:
    global _sections_indexes_created
    if _sections_indexes_created:
        return

    indexes = [
        IndexModel(
            [("course_id", ASCENDING), ("semester", ASCENDING)],
            name="course_semester",
            background=True,
        ),
        IndexModel(
            [("instructor_id", ASCENDING), ("semester", ASCENDING)],
            name="instructor_semester",
            background=True,
        ),
    ]
    collection.create_indexes(indexes)
    _sections_indexes_created = True


def get_sections_collection() -> Collection:
    """Return the class sections collection with indexes ensured."""

    collection = get_db()["class_sections"]
    _ensure_sections_indexes(collection)
    return collection


def serialize_section(document):
    """Serialize a class section document into JSON serialisable dict."""

    schedule = document.get("schedule", [])
    if not isinstance(schedule, list):
        schedule = []

    normalized_schedule = []
    for entry in schedule:
        if isinstance(entry, dict):
            dow = str(entry.get("dow", "")).strip()
            start = str(entry.get("start", "")).strip()
            end = str(entry.get("end", "")).strip()
            if dow or start or end:
                normalized_schedule.append({"dow": dow, "start": start, "end": end})
        elif isinstance(entry, str):
            text = entry.strip()
            if text:
                normalized_schedule.append({"dow": text, "start": "", "end": ""})

    return {
        "_id": str(document.get("_id", "")),
        "course_id": document.get("course_id"),
        "semester": document.get("semester"),
        "section_no": document.get("section_no"),
        "instructor_id": document.get("instructor_id"),
        "capacity": document.get("capacity"),
        "room": document.get("room"),
        "schedule": normalized_schedule,
    }


def _ensure_enrollments_indexes(collection: Collection) -> None:
    global _enrollments_indexes_created
    if _enrollments_indexes_created:
        return

    indexes = [
        IndexModel(
            [("section_id", ASCENDING)],
            name="section_id_idx",
            background=True,
        ),
        IndexModel(
            [("student_id", ASCENDING), ("semester", ASCENDING)],
            name="student_semester",
            background=True,
        ),
        IndexModel(
            [("student_id", ASCENDING), ("section_id", ASCENDING)],
            name="unique_student_section",
            unique=True,
            background=True,
        ),
    ]
    collection.create_indexes(indexes)
    _enrollments_indexes_created = True


def get_enrollments_collection() -> Collection:
    """Return the enrollments collection ensuring indexes exist."""

    collection = get_db()["enrollments"]
    _ensure_enrollments_indexes(collection)
    return collection


def serialize_enrollment(document):
    """Serialize an enrollment document for JSON responses."""

    def _score(value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return {
        "_id": str(document.get("_id", "")),
        "student_id": document.get("student_id"),
        "section_id": document.get("section_id"),
        "semester": document.get("semester"),
        "midterm": _score(document.get("midterm")),
        "final": _score(document.get("final")),
        "bonus": _score(document.get("bonus")),
        "letter": document.get("letter"),
    }


__all__ = [
    "get_db",
    "get_students_collection",
    "serialize_student",
    "get_courses_collection",
    "serialize_course",
    "get_sections_collection",
    "serialize_section",
    "get_enrollments_collection",
    "serialize_enrollment",
]
