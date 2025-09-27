from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, jsonify, request, send_from_directory
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.config import ConfigError
from src.db import get_students_collection, serialize_student

BASE_DIR = Path(__file__).resolve().parent
STATIC_FOLDER = BASE_DIR.parent / "frontend"

app = Flask(__name__, static_folder=str(STATIC_FOLDER), static_url_path="/")

logger = logging.getLogger(__name__)


def _json_error(message: str, status: int, details: Dict[str, str] | None = None):
    payload: Dict[str, Any] = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status


def _clean_string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


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
        filters: Dict[str, Any] = {}

        query = _clean_string(request.args.get("q"))
        major = _clean_string(request.args.get("major"))
        limit_arg = _clean_string(request.args.get("limit"))

        if query:
            filters["$or"] = [
                {"full_name": {"$regex": query, "$options": "i"}},
                {"email": {"$regex": query, "$options": "i"}},
            ]
        if major:
            filters["major_dept_id"] = major

        find_kwargs: Dict[str, Any] = {
            "projection": {
                "_id": 1,
                "full_name": 1,
                "email": 1,
                "major_dept_id": 1,
                "year": 1,
                "pronouns": 1,
                "phone": 1,
            },
            "sort": [("full_name", 1)],
        }

        cursor = collection.find(filters, **find_kwargs)
        if limit_arg:
            try:
                limit_value = int(limit_arg)
                if limit_value <= 0:
                    raise ValueError
                cursor = cursor.limit(limit_value)
            except ValueError:
                return _json_error("limit must be a positive integer.", 400)

        students = [serialize_student(doc) for doc in cursor]
        return jsonify(students)
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to list students", exc)


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
        created = collection.find_one({"_id": cleaned["_id"]})
        return jsonify(serialize_student(created or cleaned)), 201
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
        updated = collection.find_one({"_id": student_id})
        return jsonify(serialize_student(updated or cleaned))
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
        return jsonify({"deleted": True})
    except ConfigError as exc:
        return _handle_config_error(exc)
    except PyMongoError as exc:
        return _handle_db_error("Failed to delete student", exc)


@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/pages/<path:page>")
def pages(page: str):
    pages_dir = Path(app.static_folder) / "pages"
    return send_from_directory(str(pages_dir), page)


if __name__ == "__main__":
    app.run(debug=True)
