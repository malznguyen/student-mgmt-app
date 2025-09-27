"""Reports and analytics endpoints."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, Iterable, List, Tuple

from flask import Blueprint, Response, jsonify, request
from pymongo.errors import PyMongoError

from ..config import ConfigError
from ..db import (
    get_courses_collection,
    get_enrollments_collection,
    get_sections_collection,
    get_students_collection,
)

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")

logger = logging.getLogger(__name__)

GRADE_POINTS: Dict[str, float] = {
    "A+": 4.0,
    "A": 4.0,
    "A-": 3.7,
    "B+": 3.3,
    "B": 3.0,
    "B-": 2.7,
    "C+": 2.3,
    "C": 2.0,
    "C-": 1.7,
    "D+": 1.3,
    "D": 1.0,
    "D-": 0.7,
    "F": 0.0,
}

GRADE_ORDER: Tuple[str, ...] = (
    "A+",
    "A",
    "A-",
    "B+",
    "B",
    "B-",
    "C+",
    "C",
    "C-",
    "D+",
    "D",
    "D-",
    "F",
)

GRADE_ORDER_INDEX = {grade: index for index, grade in enumerate(GRADE_ORDER)}


def _json_error(message: str, status: int, details: Dict[str, Any] | None = None):
    payload: Dict[str, Any] = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status


def _clean_string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _normalize_semester(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    return cleaned.upper() if cleaned else None


def _format_numeric(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return int(round(number))
    return round(number, 2)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@reports_bp.get("/gpa/<student_id>")
def student_gpa(student_id: str):
    student_id_clean = _clean_string(student_id)
    if not student_id_clean:
        return _json_error("Student ID is required.", 400)

    semester = _normalize_semester(request.args.get("semester"))

    try:
        students_collection = get_students_collection()
        student_exists = students_collection.find_one({"_id": student_id_clean}, {"_id": 1})
        if not student_exists:
            return _json_error("Student not found.", 404)

        enrollments_collection = get_enrollments_collection()
        # Ensure supporting indexes exist for lookups
        get_sections_collection()
        get_courses_collection()

        match_stage: Dict[str, Any] = {"student_id": student_id_clean}
        if semester:
            match_stage["semester"] = semester

        pipeline: List[Dict[str, Any]] = [
            {"$match": match_stage},
            {
                "$lookup": {
                    "from": "class_sections",
                    "localField": "section_id",
                    "foreignField": "_id",
                    "as": "section",
                }
            },
            {"$unwind": {"path": "$section", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "courses",
                    "localField": "section.course_id",
                    "foreignField": "_id",
                    "as": "course",
                }
            },
            {"$unwind": {"path": "$course", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 0,
                    "student_id": 1,
                    "section_id": 1,
                    "semester": 1,
                    "letter": {"$ifNull": ["$letter", None]},
                    "course_id": "$section.course_id",
                    "credits": {"$ifNull": ["$course.credits", 0]},
                }
            },
        ]

        results: List[Dict[str, Any]] = list(enrollments_collection.aggregate(pipeline))

        details: List[Dict[str, Any]] = []
        quality_points = 0.0
        total_credits = 0.0

        for entry in results:
            course_id = entry.get("course_id") or ""
            section_id = entry.get("section_id") or ""
            letter_raw = entry.get("letter")
            letter = _clean_string(letter_raw).upper() if letter_raw is not None else None
            credits_value = _safe_float(entry.get("credits"))

            if credits_value < 0:
                credits_value = 0.0

            if letter and letter not in GRADE_POINTS:
                letter = None

            detail_record = {
                "course_id": course_id,
                "section_id": section_id,
                "credits": _format_numeric(credits_value) or 0,
                "letter": letter,
            }
            details.append(detail_record)

            if letter and credits_value > 0:
                total_credits += credits_value
                quality_points += GRADE_POINTS[letter] * credits_value

        details.sort(key=lambda item: (item.get("course_id") or "", item.get("section_id") or ""))

        gpa_value: float | None
        if total_credits > 0:
            gpa_value = round(quality_points / total_credits, 2)
        else:
            gpa_value = None

        payload: Dict[str, Any] = {
            "student_id": student_id_clean,
            "total_credits": _format_numeric(total_credits) or 0,
            "gpa": gpa_value,
            "details": details,
        }
        if semester:
            payload["semester"] = semester

        return jsonify(payload)
    except ConfigError as exc:
        logger.exception("Missing configuration for MongoDB")
        return _json_error(str(exc), 500)
    except PyMongoError:
        logger.exception("Failed to generate GPA report due to MongoDB error")
        return _json_error("Database unavailable. Please try again later.", 503)


@reports_bp.get("/course-stats/<course_id>")
def course_stats(course_id: str):
    course_id_clean = _clean_string(course_id)
    if not course_id_clean:
        return _json_error("Course ID is required.", 400)

    semester = _normalize_semester(request.args.get("semester"))

    try:
        courses_collection = get_courses_collection()
        course_doc = courses_collection.find_one({"_id": course_id_clean}, {"_id": 1, "title": 1})
        if not course_doc:
            return _json_error("Course not found.", 404)

        enrollments_collection = get_enrollments_collection()
        get_sections_collection()

        match_filter: Dict[str, Any] = {"section.course_id": course_id_clean}
        if semester:
            match_filter["semester"] = semester
            match_filter["section.semester"] = semester

        pipeline: List[Dict[str, Any]] = [
            {
                "$lookup": {
                    "from": "class_sections",
                    "localField": "section_id",
                    "foreignField": "_id",
                    "as": "section",
                }
            },
            {"$unwind": {"path": "$section", "preserveNullAndEmptyArrays": False}},
            {"$match": match_filter},
            {
                "$facet": {
                    "summary": [
                        {
                            "$group": {
                                "_id": None,
                                "count": {"$sum": 1},
                                "avg_midterm": {"$avg": "$midterm"},
                                "avg_final": {"$avg": "$final"},
                            }
                        }
                    ],
                    "distribution": [
                        {
                            "$group": {
                                "_id": {"$ifNull": ["$letter", ""]},
                                "count": {"$sum": 1},
                            }
                        },
                        {"$project": {"_id": 0, "letter": "$_id", "count": 1}},
                    ],
                }
            },
        ]

        aggregated = list(enrollments_collection.aggregate(pipeline))
        summary_doc = (aggregated[0]["summary"][0] if aggregated and aggregated[0]["summary"] else {})
        distribution_docs: Iterable[Dict[str, Any]]
        if aggregated:
            distribution_docs = aggregated[0].get("distribution", [])
        else:
            distribution_docs = []

        count = int(summary_doc.get("count", 0) or 0)
        avg_midterm = summary_doc.get("avg_midterm")
        avg_final = summary_doc.get("avg_final")

        distribution: List[Dict[str, Any]] = []
        for item in distribution_docs:
            letter_raw = item.get("letter")
            letter_clean = _clean_string(letter_raw).upper() if letter_raw is not None else ""
            letter_display = letter_clean if letter_clean else "N/A"
            distribution.append(
                {
                    "letter": letter_display,
                    "count": int(item.get("count", 0) or 0),
                }
            )

        distribution.sort(
            key=lambda entry: GRADE_ORDER_INDEX.get(entry["letter"], len(GRADE_ORDER_INDEX))
            if entry["letter"] != "N/A"
            else len(GRADE_ORDER_INDEX) + 1
        )

        payload: Dict[str, Any] = {
            "course_id": course_id_clean,
            "count": count,
            "avg_midterm": round(avg_midterm, 2) if isinstance(avg_midterm, (int, float)) else None,
            "avg_final": round(avg_final, 2) if isinstance(avg_final, (int, float)) else None,
            "distribution": distribution,
            "course_title": course_doc.get("title"),
        }
        if semester:
            payload["semester"] = semester

        return jsonify(payload)
    except ConfigError as exc:
        logger.exception("Missing configuration for MongoDB")
        return _json_error(str(exc), 500)
    except PyMongoError:
        logger.exception("Failed to generate course stats due to MongoDB error")
        return _json_error("Database unavailable. Please try again later.", 503)


@reports_bp.get("/enrollments.csv")
def export_enrollments_csv():
    semester = _normalize_semester(request.args.get("semester"))

    try:
        enrollments_collection = get_enrollments_collection()
        get_sections_collection()

        pipeline: List[Dict[str, Any]] = []
        match_stage: Dict[str, Any] = {}
        if semester:
            match_stage["semester"] = semester
        if match_stage:
            pipeline.append({"$match": match_stage})

        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "class_sections",
                        "localField": "section_id",
                        "foreignField": "_id",
                        "as": "section",
                    }
                },
                {"$unwind": {"path": "$section", "preserveNullAndEmptyArrays": True}},
                {
                    "$project": {
                        "_id": 0,
                        "student_id": 1,
                        "section_id": 1,
                        "course_id": "$section.course_id",
                        "semester": 1,
                        "midterm": 1,
                        "final": 1,
                        "bonus": 1,
                        "letter": {"$ifNull": ["$letter", ""]},
                    }
                },
            ]
        )

        rows = list(enrollments_collection.aggregate(pipeline))

        output = io.StringIO()
        fieldnames = [
            "student_id",
            "section_id",
            "course_id",
            "semester",
            "midterm",
            "final",
            "bonus",
            "letter",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                "student_id": row.get("student_id", ""),
                "section_id": row.get("section_id", ""),
                "course_id": row.get("course_id", ""),
                "semester": row.get("semester", ""),
                "midterm": row.get("midterm", ""),
                "final": row.get("final", ""),
                "bonus": row.get("bonus", ""),
                "letter": row.get("letter", ""),
            })

        csv_content = output.getvalue()
        filename = "enrollments.csv" if not semester else f"enrollments_{semester}.csv"

        response = Response(csv_content, mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response
    except ConfigError as exc:
        logger.exception("Missing configuration for MongoDB")
        return _json_error(str(exc), 500)
    except PyMongoError:
        logger.exception("Failed to export enrollments due to MongoDB error")
        return _json_error("Database unavailable. Please try again later.", 503)


__all__ = ["reports_bp"]
