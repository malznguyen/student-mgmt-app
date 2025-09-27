from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, send_from_directory

from src.db import get_collection

app = Flask(__name__, static_folder="../frontend", static_url_path="/")


@app.get("/api/health")
def health() -> Any:
    return jsonify({"ok": True})


@app.get("/api/students")
def list_students() -> Any:
    try:
        projection = {"_id": 1, "full_name": 1, "email": 1, "major_dept_id": 1, "year": 1}
        cursor = get_collection("students").find({}, projection)
        students = []
        for doc in cursor:
            doc["_id"] = str(doc.get("_id"))
            students.append(doc)
        return jsonify(students)
    except Exception as exc:  # pragma: no cover - logging side effect only
        app.logger.exception("Failed to fetch students", exc_info=exc)
        return jsonify({"error": "Unable to fetch students"}), 500


@app.route("/")
def root() -> Any:
    return send_from_directory(app.static_folder, "index.html")


@app.route("/pages/<path:page>")
def pages(page: str) -> Any:
    return send_from_directory(os.path.join(app.static_folder, "pages"), page)


if __name__ == "__main__":
    app.run(debug=True)
