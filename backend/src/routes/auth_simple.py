"""Simple admin authentication endpoints."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar, cast

from flask import Blueprint, jsonify, request, session

from .. import config

auth_simple_bp = Blueprint("auth_simple", __name__)

_F = TypeVar("_F", bound=Callable[..., Any])


def require_admin(func: _F) -> _F:
    """Ensure the current session belongs to the admin user."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if not session.get("is_admin"):
            return jsonify({"error": "forbidden"}), 403
        return func(*args, **kwargs)

    return cast(_F, wrapper)


@auth_simple_bp.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    if username == config.ADMIN_USER and password == config.ADMIN_PASS:
        session.clear()
        session["is_admin"] = True
        session.permanent = False
        return (
            jsonify({
                "ok": True,
                "user": {"username": config.ADMIN_USER, "role": "admin"},
            }),
            200,
        )

    session.pop("is_admin", None)
    return jsonify({"error": "invalid_credentials"}), 401


@auth_simple_bp.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@auth_simple_bp.get("/api/me")
def me():
    return jsonify({"is_admin": bool(session.get("is_admin", False))})


__all__ = ["auth_simple_bp", "require_admin"]
