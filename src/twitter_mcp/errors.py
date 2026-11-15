"""Shared error type for X API failures."""

from __future__ import annotations

from typing import Any

# X returns RFC 7807 style problem documents; keep every field that helps a
# caller understand the failure instead of collapsing it to one sentence.
_ERROR_FIELDS = ("title", "detail", "parameter", "resource_type", "resource_id", "type")


def _describe_error(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in _ERROR_FIELDS:
        value = payload.get(field)
        if value:
            parts.append(f"{field}={value}")
    if not parts:
        for key in ("error", "errors", "message"):
            value = payload.get(key)
            if value:
                parts.append(f"{key}={value}")
                break
    return "; ".join(parts)


class XApiError(RuntimeError):
    """Raised when the X API answers with a non-success status code."""

    def __init__(self, status_code: int, detail: str, method: str = "", path: str = "") -> None:
        location = f" [{method} {path}]" if method and path else ""
        super().__init__(f"X API error {status_code}{location} - {detail}")
        self.status_code = status_code
        self.detail = detail
        self.method = method
        self.path = path

    @property
    def auth_error(self) -> bool:
        return self.status_code in (401, 403)
