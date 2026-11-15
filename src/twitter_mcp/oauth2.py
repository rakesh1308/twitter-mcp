"""OAuth 2.0 client with token persistence, auto-refresh and a generic request method."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from .errors import XApiError, _describe_error

TOKEN_URL = "https://api.x.com/2/oauth2/token"
API_BASE = "https://api.x.com"


@dataclass
class OAuth2Tokens:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    expires_at: int  # epoch seconds
    scope: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OAuth2Tokens":
        return cls(
            client_id=data.get("client_id") or "",
            client_secret=data.get("client_secret") or "",
            access_token=data.get("access_token") or "",
            refresh_token=data.get("refresh_token") or "",
            expires_at=int(data.get("expires_at") or 0),
            scope=data.get("scope"),
        )


@dataclass
class OAuth2Options:
    token_file: str = "/data/oauth2.json"
    refresh_skew_seconds: int = 60


class OAuth2Client:
    def __init__(self, tokens: OAuth2Tokens, opts: OAuth2Options) -> None:
        self._tokens = tokens
        self._opts = opts
        self._client = httpx.AsyncClient(base_url=API_BASE, timeout=30.0)
        self._refresh_lock = asyncio.Lock()

    @classmethod
    def from_env(cls) -> "OAuth2Client | None":
        client_id = os.getenv("TWITTER_OAUTH2_CLIENT_ID")
        client_secret = os.getenv("TWITTER_OAUTH2_CLIENT_SECRET")
        access_token = os.getenv("TWITTER_OAUTH2_ACCESS_TOKEN")
        refresh_token = os.getenv("TWITTER_OAUTH2_REFRESH_TOKEN")
        if not (client_id and client_secret and access_token and refresh_token):
            return None

        tokens = OAuth2Tokens(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=_parse_expires(os.getenv("TWITTER_OAUTH2_EXPIRES_AT")),
            scope=os.getenv("TWITTER_OAUTH2_SCOPE"),
        )
        opts = OAuth2Options(
            token_file=os.getenv("TWITTER_OAUTH2_TOKEN_FILE") or "/data/oauth2.json",
            refresh_skew_seconds=int(os.getenv("OAUTH2_REFRESH_SKEW_SECONDS") or "60"),
        )
        client = cls(tokens, opts)
        client._load_or_seed()
        return client

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---- persistence -----------------------------------------------------

    def _load_or_seed(self) -> None:
        path = Path(self._opts.token_file)
        try:
            if path.exists():
                stored = OAuth2Tokens.from_dict(json.loads(path.read_text(encoding="utf-8")))
                access_token = stored.access_token or self._tokens.access_token
                refresh_token = stored.refresh_token or self._tokens.refresh_token
                if not access_token or not refresh_token:
                    print(f"[oauth2] token file {path} missing access/refresh token; ignoring", flush=True)
                    self._persist()
                    return
                self._tokens = OAuth2Tokens(
                    client_id=self._tokens.client_id or stored.client_id,
                    client_secret=self._tokens.client_secret or stored.client_secret,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=stored.expires_at or self._tokens.expires_at,
                    scope=stored.scope or self._tokens.scope,
                )
                print(f"[oauth2] loaded tokens from {path}", flush=True)
                return
        except Exception as err:
            print(f"[oauth2] failed to load token file: {err}", flush=True)
        self._persist()

    def _persist(self) -> None:
        path = Path(self._opts.token_file)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._tokens.to_dict(), indent=2), encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception as err:
            print(f"[oauth2] persist failed: {err}", flush=True)

    # ---- refresh ---------------------------------------------------------

    def _is_expired(self) -> bool:
        return (self._tokens.expires_at * 1000) - time.time() * 1000 < self._opts.refresh_skew_seconds * 1000

    async def _refresh(self) -> None:
        async with self._refresh_lock:
            if not self._is_expired():
                return
            auth = httpx.BasicAuth(self._tokens.client_id, self._tokens.client_secret)
            response = await self._client.post(
                TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": self._tokens.refresh_token},
                auth=auth,
            )
            if not response.is_success:
                raise XApiError(response.status_code, f"OAuth2 refresh failed: {response.text}", "POST", TOKEN_URL)
            body = response.json()
            self._tokens = OAuth2Tokens(
                client_id=self._tokens.client_id,
                client_secret=self._tokens.client_secret,
                access_token=body["access_token"],
                refresh_token=body.get("refresh_token", self._tokens.refresh_token),
                expires_at=int(time.time()) + int(body.get("expires_in", 7200)),
                scope=body.get("scope", self._tokens.scope),
            )
            self._persist()

    async def _ensure_token(self) -> str:
        await self._refresh()
        return self._tokens.access_token

    # ---- transport -------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        token = await self._ensure_token()
        response = await self._client.request(
            method,
            path,
            params=params,
            json=json_body,
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            self._tokens.expires_at = 0
            await self._refresh()
            response = await self._client.request(
                method,
                path,
                params=params,
                json=json_body,
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {self._tokens.access_token}"},
            )
        if response.status_code == 204:
            return {}
        if not response.is_success:
            raise self._error(response, method, path)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"data": response.text}

    @staticmethod
    def _error(response: httpx.Response, method: str, path: str) -> XApiError:
        detail = response.reason_phrase
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = _describe_error(payload) or detail
        except Exception:
            detail = response.text or detail
        return XApiError(response.status_code, str(detail), method, path)

    # ---- convenience -----------------------------------------------------

    async def follow_user(self, my_user_id: str, target_user_id: str) -> None:
        await self.request("POST", f"/2/users/{my_user_id}/following", json_body={"target_user_id": target_user_id})

    async def unfollow_user(self, my_user_id: str, target_user_id: str) -> None:
        await self.request("DELETE", f"/2/users/{my_user_id}/following/{target_user_id}")

    async def get_following(
        self,
        my_user_id: str,
        max_results: int = 100,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "max_results": str(max_results),
            "user.fields": "id,name,username,description,public_metrics,verified,profile_image_url",
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        return await self.request("GET", f"/2/users/{my_user_id}/following", params=params)

    async def get_followers(
        self,
        my_user_id: str,
        max_results: int = 100,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "max_results": str(max_results),
            "user.fields": "id,name,username,description,public_metrics,verified,profile_image_url",
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        return await self.request("GET", f"/2/users/{my_user_id}/followers", params=params)


def _parse_expires(raw: str | None) -> int:
    if not raw:
        return int(time.time())
    trimmed = raw.strip()
    if trimmed.isdigit():
        n = int(trimmed)
        return n // 1000 if n > 1_000_000_000_000 else n
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(trimmed.replace("Z", "++00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return int(time.time())
