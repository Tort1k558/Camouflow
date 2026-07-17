"""Cloud/team permission helpers for QML bridges."""

from __future__ import annotations

from app.services.server_client import role_allows, server_enabled


def cloud_role(app_state) -> str:
    return str(getattr(app_state, "cloudRole", "") or "")


def cloud_available(app_state) -> bool:
    if not cloud_enabled(app_state):
        return True
    return bool(getattr(app_state, "cloudAvailable", False))


def cloud_enabled(app_state) -> bool:
    if app_state is not None:
        return bool(getattr(app_state, "cloudEnabled", False) or server_enabled())
    return server_enabled()


def allows(app_state, min_role: str) -> bool:
    if not cloud_enabled(app_state):
        return True
    return cloud_available(app_state) and role_allows(cloud_role(app_state), min_role)


def deny_message(min_role: str) -> str:
    return f"Cloud role '{min_role}' or higher required"
