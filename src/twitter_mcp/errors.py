"""Shared error type for X API failures."""

from __future__ import annotations


class XApiError(RuntimeError):
    """Raised when the X API answers with a non-success status code."""

    def __init__(self, status_code: int, detail: str, method: str = "", path: str = "") -> None:
        super().__init__(f"X API error {status_code} - {detail}")
        self.status_code = status_code
        self.detail = detail
        self.method = method
        self.path = path

    @property
    def auth_error(self) -> bool:
        return self.status_code in (401, 403)
