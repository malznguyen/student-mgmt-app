"""Ensure CRUD endpoints require an admin session."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app import app


class AdminSessionRequirementTestCase(unittest.TestCase):
    """Verify that modifying endpoints cannot be used without admin login."""

    def setUp(self) -> None:
        app.config["TESTING"] = True
        self.client = app.test_client()

    def _assert_forbidden(self, method: str, path: str) -> None:
        http_method = getattr(self.client, method)
        request_kwargs = {}
        if method in {"post", "put"}:
            request_kwargs["json"] = {}

        response = http_method(path, **request_kwargs)

        self.assertEqual(403, response.status_code)
        self.assertEqual({"error": "forbidden"}, response.get_json())

    def test_crud_endpoints_require_admin(self) -> None:
        for method, path in [
            ("post", "/api/students"),
            ("put", "/api/students/s0001"),
            ("delete", "/api/students/s0001"),
            ("post", "/api/courses"),
            ("put", "/api/courses/CS101"),
            ("delete", "/api/courses/CS101"),
            ("post", "/api/sections"),
            ("put", "/api/sections/SEC1"),
            ("delete", "/api/sections/SEC1"),
            ("post", "/api/enrollments"),
            ("put", "/api/enrollments/507f1f77bcf86cd799439011"),
            ("delete", "/api/enrollments/507f1f77bcf86cd799439011"),
        ]:
            with self.subTest(method=method, path=path):
                self._assert_forbidden(method, path)


if __name__ == "__main__":
    unittest.main()
