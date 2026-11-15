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
        hint = hint_for(status_code, method, path, detail)
        message = f"X API error {status_code}{location} - {detail}"
        if hint:
            message = f"{message}. {hint}"
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
        self.method = method
        self.path = path

    @property
    def auth_error(self) -> bool:
        return self.status_code in (401, 403)


class OAuth2Unavailable(RuntimeError):
    """Raised when the OAuth 2.0 transport cannot be used at all."""


_HINTS: list[tuple[str, str, str]] = [
    (
        "POST",
        "/2/tweets",
        "X rejected the post. Check that the app has Read and write permissions, that the developer account has "
        "an active credit balance (GET /2/usage/credits) and that the token carries tweet.write - for OAuth 2.0 "
        "re-authorize with the scope string in the README",
    ),
    (
        "GET",
        "/2/tweets/search/all",
        "Full archive search needs a project with full archive access on the current pay-per-use pricing",
    ),
    (
        "GET",
        "/2/tweets/counts/all",
        "Full archive counts need a project with full archive access on the current pay-per-use pricing",
    ),
]


def hint_for(status_code: int, method: str, path: str, detail: str = "") -> str:
    """Actionable guidance for the X API failures that are easy to misread."""
    if "unsupported authentication" in detail.lower():
        return (
            "This endpoint only accepts OAuth 2.0. If OAuth 2.0 is configured but unusable, re-authorize with "
            "scripts/oauth2_bootstrap.py and update TWITTER_OAUTH2_ACCESS_TOKEN and TWITTER_OAUTH2_REFRESH_TOKEN"
        )
    for hint_method, hint_path, hint_text in _HINTS:
        if method.upper() == hint_method and path.startswith(hint_path):
            if status_code in (400, 403):
                return hint_text
    return ""
