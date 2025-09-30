"""Application route blueprints and helpers."""

from .auth_simple import auth_simple_bp, require_admin
from .reports import reports_bp

__all__ = ["auth_simple_bp", "reports_bp", "require_admin"]
