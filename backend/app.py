from __future__ import annotations
import logging
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from pymongo.errors import PyMongoError

from src.config import ConfigError
from src.db import get_students_collection, serialize_student

BASE_DIR = Path(__file__).resolve().parent
STATIC_FOLDER = BASE_DIR.parent / "frontend"

app = Flask(__name__, static_folder=str(STATIC_FOLDER), static_url_path="/")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/students")
def list_students():
    try:
        collection = get_students_collection()
        cursor = collection.find(
            {},
            {
                "_id": 1,
                "full_name": 1,
                "email": 1,
                "major_dept_id": 1,
                "year": 1,
                "pronouns": 1,
            },
        )
        students = [serialize_student(doc) for doc in cursor]
    except ConfigError as exc:
        logging.exception("Missing configuration for MongoDB")
        return jsonify({"error": str(exc)}), 500
    except PyMongoError:
        logging.exception("Failed to fetch students from MongoDB")
        return jsonify({"error": "Unable to load students"}), 500

    return jsonify(students)


@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/pages/<path:page>")
def pages(page: str):
    pages_dir = Path(app.static_folder) / "pages"
    return send_from_directory(str(pages_dir), page)


if __name__ == "__main__":
    app.run(debug=True)
