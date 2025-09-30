from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Flask, jsonify, request, send_from_directory
from pymongo.errors import DuplicateKeyError, PyMongoError
from bson import ObjectId
from bson.errors import InvalidId

from src import config
from src.config import ConfigError
from src.db import (
    get_courses_collection,
    get_enrollments_collection,
    get_sections_collection,
    get_students_collection,
    serialize_course,
    serialize_enrollment,
    serialize_section,
    serialize_student,
    get_db,
)
from src.routes import auth_simple_bp, reports_bp, require_admin
from src.utils.paging import PagingParamError, parse_paging_params

BASE_DIR = Path(__file__).resolve().parent
STATIC_FOLDER = BASE_DIR.parent / "frontend"

app = Flask(__name__, static_folder=str(STATIC_FOLDER), static_url_path="/")
app.secret_key = config.SECRET_KEY
app.config["SESSION_COOKIE_NAME"] = config.SESSION_COOKIE_NAME

# Authentication endpoints remain for optional use, but CRUD routes no longer
# require an admin session.
app.register_blueprint(auth_simple_bp)
app.register_blueprint(reports_bp)

logger = logging.getLogger(__name__)


def _json_error(message: str, status: int, details: Dict[str, str] | None = None):
    payload: Dict[str, Any] = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status


def _clean_string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _clean_string_or_none(value: Any) -> str | None:
    cleaned = _clean_string(value)
    return cleaned if cleaned else None


def _parse_limit_arg(
    limit_arg: str | None, *, default: int | None = None
) -> int | None:
    if not limit_arg:
        if default is None:
            return None
        if default <= 0:
            raise ValueError("limit must be a positive integer.")
        return default
    try:
        value = int(limit_arg)
    except (TypeError, ValueError):
        raise ValueError("limit must be a positive integer.")
    if value <= 0:
        raise ValueError("limit must be a positive integer.")
    return value


def _calculate_letter_grade(
    midterm: float | None, final: float | None, bonus: float | None
) -> str | None:
    if midterm is None or final is None:
        return None

    bonus_value = bonus or 0.0
    total = 0.4 * midterm + 0.6 * final + bonus_value
    total = max(0.0, min(total, 10.0))
    total = round(total, 2)

    grade_scale: List[Tuple[float, str]] = [
        (8.5, "A"),
        (8.0, "A-"),
        (7.5, "B+"),
        (7.0, "B"),
        (6.5, "B-"),
        (6.0, "C+"),
        (5.5, "C"),
        (5.0, "D"),
    ]

    for threshold, letter in grade_scale:
        if total >= threshold:
            return letter
    return "F"


def _validate_student_payload(
    payload: Dict[str, Any] | None, *, require_all: bool
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    if payload is None:
        return {}, {"_global": "Request body must be JSON."}

    errors: Dict[str, str] = {}
    cleaned: Dict[str, Any] = {}

    def require_field(field: str, message: str) -> bool:
        if field not in payload or _clean_string(payload.get(field)) == "":
            errors[field] = message
            return False
        return True

    if require_all or "_id" in payload:
        if require_field("_id", "Student ID is required."):
            cleaned["_id"] = _clean_string(payload.get("_id"))

    if require_all or "full_name" in payload:
        if require_field("full_name", "Full name is required."):
            cleaned["full_name"] = _clean_string(payload.get("full_name"))

    if require_all or "email" in payload:
        if require_field("email", "Email is required."):
            email = _clean_string(payload.get("email"))
            if "@" not in email or "." not in email.split("@")[-1]:
                errors["email"] = "Enter a valid email address."
            else:
                cleaned["email"] = email.lower()

    if require_all or "major_dept_id" in payload:
        if require_field("major_dept_id", "Major department is required."):
            cleaned["major_dept_id"] = _clean_string(payload.get("major_dept_id"))

    if require_all or "year" in payload:
        if require_field("year", "Graduation year is required."):
            try:
                cleaned["year"] = int(_clean_string(payload.get("year")))
            except (TypeError, ValueError):
                errors["year"] = "Graduation year must be a number."

    if "pronouns" in payload:
        cleaned["pronouns"] = _clean_string(payload.get("pronouns"))

    if "phone" in payload:
        cleaned["phone"] = _clean_string(payload.get("phone"))

    # Remove keys with None values so we don't overwrite with null unless explicit
    cleaned = {k: v for k, v in cleaned.items() if v is not None}

    return cleaned, errors


def _validate_course_payload(
    payload: Dict[str, Any] | None, *, require_all: bool
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    if payload is None:
        return {}, {"_global": "Request body must be JSON."}

    errors: Dict[str, str] = {}
    cleaned: Dict[str, Any] = {}

    def require_field(field: str, message: str) -> bool:
        if field not in payload or _clean_string(payload.get(field)) == "":
            errors[field] = message
            return False
        return True

    if require_all or "_id" in payload:
        if require_field("_id", "Course ID is required."):
            cleaned["_id"] = _clean_string(payload.get("_id"))

    if require_all or "title" in payload:
        if require_field("title", "Course title is required."):
            cleaned["title"] = _clean_string(payload.get("title"))

    if require_all or "dept_id" in payload:
        if require_field("dept_id", "Department code is required."):
            cleaned["dept_id"] = _clean_string(payload.get("dept_id"))

    if require_all or "credits" in payload:
        if "credits" not in payload or payload.get("credits") in (None, ""):
            if require_all:
                errors["credits"] = "Credits are required."
        else:
            try:
                credits_value_raw = payload.get("credits")
                credits_value = int(float(credits_value_raw))
                if credits_value <= 0:
                    raise ValueError
                cleaned["credits"] = credits_value
            except (TypeError, ValueError):
                errors["credits"] = "Credits must be a positive integer."

    if "prereq_ids" in payload:
        prereqs = payload.get("prereq_ids")
        if prereqs in (None, ""):
            cleaned["prereq_ids"] = []
        elif isinstance(prereqs, list):
            cleaned["prereq_ids"] = [
                _clean_string(value) for value in prereqs if _clean_string(value)
            ]
        elif isinstance(prereqs, str):
            cleaned["prereq_ids"] = [
                part.strip() for part in prereqs.split(",") if part.strip()
            ]
        else:
            errors["prereq_ids"] = "Prerequisites must be an array of course IDs."

    cleaned = {k: v for k, v in cleaned.items() if v is not None}
    return cleaned, errors


def _validate_section_payload(
    payload: Dict[str, Any] | None, *, require_all: bool
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    if payload is None:
        return {}, {"_global": "Request body must be JSON."}

    errors: Dict[str, str] = {}
    cleaned: Dict[str, Any] = {}

    def _assign_required(field: str, message: str, transform=None) -> None:
        should_validate = require_all or field in payload
        if not should_validate:
            return

        value = _clean_string(payload.get(field))
        if value == "":
            errors[field] = message
            return

        cleaned[field] = transform(value) if callable(transform) else value

    _assign_required("_id", "Section ID is required.")
    _assign_required("course_id", "Course ID is required.")
    _assign_required("semester", "Semester is required.", lambda v: v.upper())
    _assign_required("section_no", "Section number is required.")

    instructor_val = payload.get("instructor_id") if payload else None
    if instructor_val not in (None, ""):
        cleaned["instructor_id"] = _clean_string(instructor_val)

    if "capacity" in payload and payload.get("capacity") not in (None, ""):
        try:
            capacity_value = int(float(payload.get("capacity")))
            if capacity_value < 0:
                raise ValueError
            cleaned["capacity"] = capacity_value
        except (TypeError, ValueError):
            errors["capacity"] = "Capacity must be a non-negative number."

    room_val = payload.get("room") if payload else None
    if room_val not in (None, ""):
        cleaned["room"] = _clean_string(room_val)

    if "schedule" in payload:
        schedule = payload.get("schedule")
        if schedule in (None, ""):
            cleaned["schedule"] = []
        elif isinstance(schedule, list):
            normalized_schedule = []
            for index, entry in enumerate(schedule):
                if not isinstance(entry, dict):
                    errors[f"schedule[{index}]"] = "Schedule entries must be objects."
                    continue

                dow = _clean_string(entry.get("dow"))
                start = _clean_string(entry.get("start"))
                end = _clean_string(entry.get("end"))

                if not dow or not start or not end:
                    errors[f"schedule[{index}]"] = "Dow, start, and end are required."
                    continue

                normalized_schedule.append({"dow": dow, "start": start, "end": end})

            cleaned["schedule"] = normalized_schedule
        else:
            errors["schedule"] = "Schedule must be an array of meeting entries."

    cleaned = {k: v for k, v in cleaned.items() if v is not None}
    return cleaned, errors


def _validate_enrollment_payload(
    payload: Dict[str, Any] | None, *, require_all: bool
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    if payload is None:
        return {}, {"_global": "Request body must be JSON."}

    errors: Dict[str, str] = {}
    cleaned: Dict[str, Any] = {}

    def require_field(field: str, message: str) -> bool:
        if field not in payload or _clean_string(payload.get(field)) == "":
            errors[field] = message
            return False
        return True

    if require_all or "student_id" in payload:
        if require_field("student_id", "Student ID is required."):
            cleaned["student_id"] = _clean_string(payload.get("student_id"))

    if require_all or "section_id" in payload:
        if require_field("section_id", "Section ID is required."):
            cleaned["section_id"] = _clean_string(payload.get("section_id"))

    if require_all or "semester" in payload:
        if require_field("semester", "Semester is required."):
            cleaned["semester"] = _clean_string(payload.get("semester")).upper()

    score_ranges = {
        "midterm": (0.0, 10.0),
        "final": (0.0, 10.0),
        "bonus": (0.0, 2.0),
    }

    for field, (minimum, maximum) in score_ranges.items():
        if field not in payload:
            continue

        value = payload.get(field)
        if value in (None, ""):
            cleaned[field] = None
            continue

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            errors[field] = "Scores must be numeric."
            continue

        if numeric_value < minimum or numeric_value > maximum:
            errors[field] = f"{field.capitalize()} must be between {minimum:g} and {maximum:g}."
            continue

        cleaned[field] = round(numeric_value, 2)

    return cleaned, errors


def _handle_config_error(exc: ConfigError):
    logger.exception("Missing configuration for MongoDB")
    return _json_error(str(exc), 500)


def _handle_db_error(action: str, exc: PyMongoError):
    logger.exception("%s due to MongoDB error", action)
    return _json_error("Database unavailable. Please try again later.", 503)


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/students")
def list_students():
    try:
        collection = get_students_collection()

        try:
            paging = parse_paging_params(
                request.args,
                allowed_sort_fields={"full_name": "full_name", "year": "year"},
                default_sort="full_name",
            )
        except PagingParamError as exc:
            return _json_error(str(exc), 400)

        filters: Dict[str, Any] = {}

        query = _clean_string(request.args.get("q"))
        major = _clean_string(request.args.get("major"))
        year_raw = _clean_string(request.args.get("year"))

        if query:
            filters["$or"] = [
                {"full_name": {"$regex": query, "$options": "i"}},
                {"email": {"$regex": query, "$options": "i"}},
            ]
        if major:
            filters["major_dept_id"] = major
        if year_raw:
            try:
                filters["year"] = int(year_raw)
            except ValueError:
                return _json_error("year must be an integer.", 400)

        projection = {
            "_id": 1,
            "full_name": 1,
            "email": 1,
            "major_dept_id": 1,
            "year": 1,
            "phone": 1,
            "pronouns": 1,
        }

        total = collection.count_documents(filters)

        page = paging.page
        page_size = paging.page_size
        max_page = (total + page_size - 1) // page_size if total else 0

        if max_page == 0:
            page = 1
        elif page > max_page:
            page = max_page

        skip = (page - 1) * page_size if total else 0

        cursor = (
            collection.find(filters, projection=projection)
            .sort([paging.sort])
            .skip(skip)
            .limit(page_size)
        )

        items = [serialize_student(doc) for doc in cursor]

        has_next = page < max_page if max_page else False
        has_prev = page > 1

        return jsonify(
            {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": has_next,
                "has_prev": has_prev,
            }
        )
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError:
        logger.exception("Failed to list students due to MongoDB error")
        return jsonify({"error": "unavailable"}), 503


@app.post("/api/students")
def create_student():
    data = request.get_json(silent=True)
    cleaned, errors = _validate_student_payload(data, require_all=True)
    if errors:
        details = {k: v for k, v in errors.items() if k != "_global"}
        message = errors.get("_global", "Validation failed.")
        return _json_error(message, 400, details if details else None)

    try:
        collection = get_students_collection()
        collection.insert_one(cleaned)
        return jsonify({"ok": True}), 201
    except ConfigError as exc:
        return _handle_config_error(exc)
    except DuplicateKeyError as exc:
        logger.exception("Duplicate key error while creating student")
        return _json_error(
            "A student with this email or ID already exists.",
            409,
            {"email": "Email already in use."},
        )
    except PyMongoError as exc:
        return _handle_db_error("Failed to create student", exc)


@app.put("/api/students/<student_id>")
def update_student(student_id: str):
    data = request.get_json(silent=True)
    cleaned, errors = _validate_student_payload(data, require_all=False)

    if "_id" in cleaned and cleaned["_id"] != student_id:
        errors["_id"] = "Student ID cannot be changed."

    if errors:
        return _json_error("Validation failed.", 400, errors)

    if not cleaned:
        return _json_error("No changes supplied.", 400)

    try:
        collection = get_students_collection()
        result = collection.update_one({"_id": student_id}, {"$set": cleaned})
        if result.matched_count == 0:
            return _json_error("Student not found.", 404)
        return jsonify({"ok": True})
    except ConfigError as exc:
        return _handle_config_error(exc)
    except DuplicateKeyError as exc:
        logger.exception("Duplicate key error while updating student")
        return _json_error(
            "A student with this email already exists.",
            409,
            {"email": "Email already in use."},
        )
    except PyMongoError as exc:
        return _handle_db_error("Failed to update student", exc)


@app.delete("/api/students/<student_id>")
def delete_student(student_id: str):
    try:
        collection = get_students_collection()
        result = collection.delete_one({"_id": student_id})
        if result.deleted_count == 0:
            return _json_error("Student not found.", 404)
        return jsonify({"ok": True})
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to delete student", exc)


@app.get("/api/courses")
def list_courses():
    try:
        collection = get_courses_collection()
        filters: Dict[str, Any] = {}

        query = _clean_string(request.args.get("q"))
        dept = _clean_string(request.args.get("dept"))
        limit_arg = request.args.get("limit")

        if query:
            filters["title"] = {"$regex": query, "$options": "i"}
        if dept:
            filters["dept_id"] = dept

        projection = {
            "_id": 1,
            "title": 1,
            "dept_id": 1,
            "credits": 1,
            "prereq_ids": 1,
        }

        cursor = collection.find(filters, projection=projection, sort=[("title", 1)])
        try:
            limit_value = _parse_limit_arg(limit_arg)
        except ValueError as exc:
            return _json_error(str(exc), 400)
        limit_value = limit_value or 100
        cursor = cursor.limit(limit_value)

        courses = []
        for doc in cursor:
            serialized = serialize_course(doc)
            serialized["prereq_ids"] = serialized.get("prereq_ids") or []
            courses.append(serialized)
        return jsonify(courses)
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to list courses", exc)


@app.post("/api/courses")
def create_course():
    data = request.get_json(silent=True)
    cleaned, errors = _validate_course_payload(data, require_all=True)
    if errors:
        details = {k: v for k, v in errors.items() if k != "_global"}
        message = errors.get("_global", "Validation failed.")
        return _json_error(message, 400, details if details else None)

    try:
        collection = get_courses_collection()
        collection.insert_one(cleaned)
        return jsonify({"ok": True}), 201
    except ConfigError as exc:
        return _handle_config_error(exc)
    except DuplicateKeyError:
        return _json_error(
            "Course with this ID already exists.",
            409,
            {"_id": "Choose a different course ID."},
        )
    except PyMongoError as exc:
        return _handle_db_error("Failed to create course", exc)


@app.put("/api/courses/<course_id>")
def update_course(course_id: str):
    data = request.get_json(silent=True)
    cleaned, errors = _validate_course_payload(data, require_all=False)

    if "_id" in cleaned and cleaned["_id"] != course_id:
        errors["_id"] = "Course ID cannot be changed."

    if errors:
        return _json_error("Validation failed.", 400, errors)

    if not cleaned:
        return _json_error("No changes supplied.", 400)

    try:
        collection = get_courses_collection()
        result = collection.update_one({"_id": course_id}, {"$set": cleaned})
        if result.matched_count == 0:
            return _json_error("Course not found.", 404)
        return jsonify({"ok": True})
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to update course", exc)


@app.delete("/api/courses/<course_id>")
def delete_course(course_id: str):
    try:
        collection = get_courses_collection()
        result = collection.delete_one({"_id": course_id})
        if result.deleted_count == 0:
            return _json_error("Course not found.", 404)
        return jsonify({"ok": True})
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to delete course", exc)


@app.get("/api/sections")
def list_sections():
    try:
        collection = get_sections_collection()
        filters: Dict[str, Any] = {}

        course_id = _clean_string(request.args.get("course_id"))
        semester = _clean_string(request.args.get("semester"))
        instructor_id = _clean_string(request.args.get("instructor_id"))
        query = _clean_string(request.args.get("q"))
        limit_arg = request.args.get("limit")

        if course_id:
            filters["course_id"] = course_id
        if semester:
            filters["semester"] = semester.upper()
        if instructor_id:
            filters["instructor_id"] = instructor_id
        if query:
            filters["$or"] = [
                {"_id": {"$regex": query, "$options": "i"}},
                {"course_id": {"$regex": query, "$options": "i"}},
            ]

        projection = {
            "_id": 1,
            "course_id": 1,
            "semester": 1,
            "section_no": 1,
            "instructor_id": 1,
            "capacity": 1,
            "room": 1,
            "schedule": 1,
        }

        cursor = collection.find(
            filters,
            projection=projection,
            sort=[("semester", -1), ("section_no", 1)],
        )
        try:
            limit_value = _parse_limit_arg(limit_arg, default=200)
        except ValueError as exc:
            return _json_error(str(exc), 400)
        if limit_value:
            cursor = cursor.limit(limit_value)

        sections = list(cursor)
        course_ids = {doc.get("course_id") for doc in sections if doc.get("course_id")}
        courses_map: Dict[str, Dict[str, Any]] = {}
        if course_ids:
            courses_cursor = get_courses_collection().find(
                {"_id": {"$in": list(course_ids)}},
                projection={"_id": 1, "title": 1, "dept_id": 1, "credits": 1},
            )
            courses_map = {doc["_id"]: doc for doc in courses_cursor}

        payload: List[Dict[str, Any]] = []
        for doc in sections:
            serialized = serialize_section(doc)
            course = courses_map.get(serialized["course_id"])
            serialized["course_title"] = course.get("title") if course else None
            serialized["course_dept_id"] = course.get("dept_id") if course else None
            serialized["course_credits"] = course.get("credits") if course else None
            payload.append(serialized)

        return jsonify(payload)
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to list sections", exc)


def _ensure_course_exists(course_id: str) -> bool:
    courses_collection = get_courses_collection()
    return bool(courses_collection.find_one({"_id": course_id}, projection={"_id": 1}))


@app.post("/api/sections")
def create_section():
    data = request.get_json(silent=True)
    cleaned, errors = _validate_section_payload(data, require_all=True)
    if errors:
        details = {k: v for k, v in errors.items() if k != "_global"}
        message = errors.get("_global", "Validation failed.")
        return _json_error(message, 400, details if details else None)

    try:
        if not _ensure_course_exists(cleaned["course_id"]):
            return _json_error(
                "Course not found.",
                404,
                {"course_id": "Select an existing course."},
            )

        collection = get_sections_collection()
        collection.insert_one(cleaned)
        created = collection.find_one({"_id": cleaned["_id"]})
        response = serialize_section(created or cleaned)
        course_doc = get_courses_collection().find_one(
            {"_id": response["course_id"]}, projection={"title": 1, "dept_id": 1, "credits": 1}
        )
        if course_doc:
            response["course_title"] = course_doc.get("title")
            response["course_dept_id"] = course_doc.get("dept_id")
            response["course_credits"] = course_doc.get("credits")
        return jsonify(response), 201
    except ConfigError as exc:
        return _handle_config_error(exc)
    except DuplicateKeyError:
        return _json_error("Section with this ID already exists.", 409, {"_id": "Choose a different section ID."})
    except PyMongoError as exc:
        return _handle_db_error("Failed to create section", exc)


@app.put("/api/sections/<section_id>")
def update_section(section_id: str):
    data = request.get_json(silent=True)
    cleaned, errors = _validate_section_payload(data, require_all=False)

    if "_id" in cleaned:
        if cleaned["_id"] != section_id:
            errors["_id"] = "Section ID cannot be changed."
        cleaned.pop("_id", None)

    if errors:
        return _json_error("Validation failed.", 400, errors)

    if not cleaned:
        return _json_error("No changes supplied.", 400)

    try:
        if "course_id" in cleaned and not _ensure_course_exists(cleaned["course_id"]):
            return _json_error(
                "Course not found.",
                404,
                {"course_id": "Select an existing course."},
            )

        collection = get_sections_collection()
        result = collection.update_one({"_id": section_id}, {"$set": cleaned})
        if result.matched_count == 0:
            return _json_error("Section not found.", 404)

        updated = collection.find_one({"_id": section_id})
        response = serialize_section(updated or cleaned)
        course_doc = None
        if response.get("course_id"):
            course_doc = get_courses_collection().find_one(
                {"_id": response["course_id"]}, projection={"title": 1, "dept_id": 1, "credits": 1}
            )
        if course_doc:
            response["course_title"] = course_doc.get("title")
            response["course_dept_id"] = course_doc.get("dept_id")
            response["course_credits"] = course_doc.get("credits")
        return jsonify(response)
    except ConfigError as exc:
        return _handle_config_error(exc)
    except DuplicateKeyError:
        return _json_error("Section with this ID already exists.", 409, {"_id": "Choose a different section ID."})
    except PyMongoError as exc:
        return _handle_db_error("Failed to update section", exc)


@app.delete("/api/sections/<section_id>")
def delete_section(section_id: str):
    try:
        collection = get_sections_collection()
        result = collection.delete_one({"_id": section_id})
        if result.deleted_count == 0:
            return _json_error("Section not found.", 404)
        enrollments_collection = get_enrollments_collection()
        affected = enrollments_collection.count_documents({"section_id": section_id})
        return jsonify({"deleted": True, "enrollments": affected})
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to delete section", exc)


def _ensure_student_exists(student_id: str) -> bool:
    collection = get_students_collection()
    return bool(collection.find_one({"_id": student_id}, projection={"_id": 1}))


def _candidate_enrollment_filters(enrollment_id: str) -> List[Dict[str, Any]]:
    filters: List[Dict[str, Any]] = [{"_id": enrollment_id}]
    try:
        filters.append({"_id": ObjectId(enrollment_id)})
    except (InvalidId, TypeError):
        pass
    return filters


def _ensure_section_exists(section_id: str, semester: str) -> bool:
    collection = get_sections_collection()
    return bool(
        collection.find_one(
            {"_id": section_id, "semester": semester},
            projection={"_id": 1},
        )
    )


@app.get("/api/enrollments")
def list_enrollments():
    try:
        collection = get_enrollments_collection()
        filters: Dict[str, Any] = {}

        student_id = _clean_string(request.args.get("student_id"))
        section_id = _clean_string(request.args.get("section_id"))
        semester = _clean_string(request.args.get("semester"))
        limit_arg = _clean_string(request.args.get("limit"))

        if student_id:
            filters["student_id"] = student_id
        if section_id:
            filters["section_id"] = section_id
        if semester:
            filters["semester"] = semester.upper()
        try:
            limit_value = _parse_limit_arg(limit_arg, default=200)
        except ValueError as exc:
            return _json_error(str(exc), 400)

        cursor = collection.find(filters, sort=[("semester", -1), ("student_id", 1)])
        if limit_value is not None:
            cursor = cursor.limit(limit_value)

        payload = [serialize_enrollment(doc) for doc in cursor]
        return jsonify(payload)
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to list enrollments", exc)


@app.post("/api/enrollments")
def create_enrollment():
    data = request.get_json(silent=True)
    cleaned, errors = _validate_enrollment_payload(data, require_all=True)
    if errors:
        details = {k: v for k, v in errors.items() if k != "_global"}
        message = errors.get("_global", "Validation failed.")
        return _json_error(message, 400, details if details else None)

    try:
        if not _ensure_student_exists(cleaned["student_id"]):
            return _json_error("Student not found.", 404)

        if not _ensure_section_exists(cleaned["section_id"], cleaned["semester"]):
            return _json_error("Class section not found for the specified semester.", 404)

        document: Dict[str, Any] = {
            "student_id": cleaned["student_id"],
            "section_id": cleaned["section_id"],
            "semester": cleaned["semester"],
        }

        for field in ("midterm", "final", "bonus"):
            value = cleaned.get(field)
            if value is not None:
                document[field] = value

        letter = _calculate_letter_grade(
            document.get("midterm"), document.get("final"), document.get("bonus")
        )
        if letter is not None:
            document["letter"] = letter

        collection = get_enrollments_collection()
        result = collection.insert_one(document)

        return jsonify({"ok": True, "id": str(result.inserted_id)}), 201
    except ConfigError as exc:
        return _handle_config_error(exc)
    except DuplicateKeyError:
        return _json_error("Enrollment already exists for this student and section.", 409)
    except PyMongoError as exc:
        return _handle_db_error("Failed to create enrollment", exc)


@app.put("/api/enrollments/<enrollment_id>")
def update_enrollment(enrollment_id: str):
    data = request.get_json(silent=True)
    cleaned, errors = _validate_enrollment_payload(data, require_all=False)

    if "student_id" in cleaned:
        errors["student_id"] = "Student cannot be changed."
        cleaned.pop("student_id", None)

    if errors:
        return _json_error("Validation failed.", 400, errors)

    if not cleaned:
        return _json_error("No changes supplied.", 400)

    try:
        collection = get_enrollments_collection()
        existing: Dict[str, Any] | None = None
        match_filter: Dict[str, Any] | None = None
        for candidate in _candidate_enrollment_filters(enrollment_id):
            doc = collection.find_one(candidate)
            if doc:
                existing = doc
                match_filter = candidate
                break

        if not existing or match_filter is None:
            return _json_error("Enrollment not found.", 404)

        grade_fields = ("midterm", "final", "bonus")

        if "section_id" in cleaned or "semester" in cleaned:
            next_section_id = cleaned.get("section_id", existing.get("section_id"))
            next_semester = cleaned.get("semester", existing.get("semester"))
            if not _ensure_section_exists(next_section_id, next_semester):
                return _json_error("Class section not found for the specified semester.", 404)

        update_fields: Dict[str, Any] = {}
        unset_fields: Dict[str, str] = {}
        combined = existing.copy()

        for field in ("semester", "section_id"):
            if field in cleaned:
                combined[field] = cleaned[field]
                update_fields[field] = cleaned[field]

        for field in grade_fields:
            if field in cleaned:
                value = cleaned[field]
                combined[field] = value
                if value is None:
                    unset_fields[field] = ""
                    update_fields.pop(field, None)
                else:
                    update_fields[field] = value
                    unset_fields.pop(field, None)

        if any(field in cleaned for field in grade_fields):
            letter = _calculate_letter_grade(
                combined.get("midterm"), combined.get("final"), combined.get("bonus")
            )
            if letter is not None:
                update_fields["letter"] = letter
                unset_fields.pop("letter", None)
            else:
                unset_fields["letter"] = ""
                update_fields.pop("letter", None)

        if not update_fields and not unset_fields:
            return _json_error("No changes supplied.", 400)

        update_doc: Dict[str, Any] = {}
        if update_fields:
            update_doc["$set"] = update_fields
        if unset_fields:
            update_doc["$unset"] = unset_fields

        result = collection.update_one(match_filter, update_doc)
        if result.matched_count == 0:
            return _json_error("Enrollment not found.", 404)

        return jsonify({"ok": True})
    except ConfigError as exc:
        return _handle_config_error(exc)
    except DuplicateKeyError:
        return _json_error("Enrollment already exists for this student and section.", 409)
    except PyMongoError as exc:
        return _handle_db_error("Failed to update enrollment", exc)


@app.delete("/api/enrollments/<enrollment_id>")
def delete_enrollment(enrollment_id: str):
    try:
        collection = get_enrollments_collection()
        deleted = 0
        for candidate in _candidate_enrollment_filters(enrollment_id):
            result = collection.delete_one(candidate)
            if result.deleted_count:
                deleted = result.deleted_count
                break

        if deleted == 0:
            return _json_error("Enrollment not found.", 404)
        return jsonify({"ok": True})
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to delete enrollment", exc)


@app.get("/api/stats")
def stats():
    try:
        get_db()  # Ensure the database connection is available

        students_collection = get_students_collection()
        enrollments_collection = get_enrollments_collection()

        students_pipeline = [
            {
                "$group": {
                    "_id": {"$ifNull": ["$major_dept_id", "UNDECLARED"]},
                    "count": {"$sum": 1},
                }
            },
            {"$project": {"_id": 0, "major_dept_id": "$_id", "count": 1}},
            {"$sort": {"count": -1, "major_dept_id": 1}},
        ]

        students_by_major = list(students_collection.aggregate(students_pipeline))

        enrollments_pipeline = [
            {
                "$group": {
                    "_id": {"$ifNull": ["$semester", "UNKNOWN"]},
                    "count": {"$sum": 1},
                }
            },
            {"$project": {"_id": 0, "semester": "$_id", "count": 1}},
            {"$sort": {"semester": 1}},
        ]

        enrollments_by_semester = list(
            enrollments_collection.aggregate(enrollments_pipeline)
        )

        top_courses_pipeline = [
            {
                "$lookup": {
                    "from": "class_sections",
                    "localField": "section_id",
                    "foreignField": "_id",
                    "as": "section",
                }
            },
            {"$unwind": "$section"},
            {
                "$group": {
                    "_id": "$section.course_id",
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 5},
            {
                "$lookup": {
                    "from": "courses",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "course",
                }
            },
            {
                "$unwind": {
                    "path": "$course",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "course_id": "$_id",
                    "count": 1,
                    "title": {"$ifNull": ["$course.title", "$_id"]},
                }
            },
        ]

        top_courses_by_enrollment = list(
            enrollments_collection.aggregate(top_courses_pipeline)
        )

        payload = {
            "students_by_major": students_by_major,
            "enrollments_by_semester": enrollments_by_semester,
            "top_courses_by_enrollment": top_courses_by_enrollment,
        }

        return jsonify(payload)
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to load stats", exc)


@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/pages/<path:page>")
def pages(page: str):
    pages_dir = Path(app.static_folder) / "pages"
    return send_from_directory(str(pages_dir), page)


if __name__ == "__main__":
    app.run(debug=True)
