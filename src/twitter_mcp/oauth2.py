"""OAuth 2.0 client with token persistence and auto-refresh."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
API_BASE = "https://api.twitter.com/2"


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
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=int(data["expires_at"]),
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
        self._client = httpx.Client(base_url=API_BASE, timeout=30.0)
        self._refresh_lock = False

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

    def close(self) -> None:
        self._client.close()

    # ---- persistence -----------------------------------------------------

    def _load_or_seed(self) -> None:
        path = Path(self._opts.token_file)
        try:
            if path.exists():
                stored = OAuth2Tokens.from_dict(json.loads(path.read_text(encoding="utf-8")))
                self._tokens = OAuth2Tokens(
                    client_id=self._tokens.client_id,
                    client_secret=self._tokens.client_secret,
                    access_token=stored.access_token or self._tokens.access_token,
                    refresh_token=stored.refresh_token or self._tokens.refresh_token,
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

    # ---- refresh ----------------------------------------------------------

    def _is_expired(self) -> bool:
        return (self._tokens.expires_at * 1000) - time.time() * 1000 < self._opts.refresh_skew_seconds * 1000

    async def _refresh_async(self) -> None:
        auth = httpx.BasicAuth(self._tokens.client_id, self._tokens.client_secret)
        response = await self._client_async.post(
            TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._tokens.refresh_token},
            auth=auth,
        )
        if not response.is_success:
            raise RuntimeError(f"OAuth2 refresh failed: {response.status_code} {response.text}")
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

    @property
    def _client_async(self) -> httpx.AsyncClient:
        if not hasattr(self, "_async_client") or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(base_url=API_BASE, timeout=30.0)
        return self._async_client

    async def _ensure_token(self) -> str:
        if self._is_expired():
            await self._refresh_async()
        return self._tokens.access_token

    # ---- API --------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        await self._ensure_token()
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {self._tokens.access_token}"
        if "json" in kwargs and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        response = await self._client_async.request(method, path, headers=headers, **kwargs)
        if response.status_code == 401:
            await self._refresh_async()
            headers["Authorization"] = f"Bearer {self._tokens.access_token}"
            response = await self._client_async.request(method, path, headers=headers, **kwargs)
        if not response.is_success and response.status_code != 204:
            detail = response.reason_phrase
            try:
                data = response.json()
                if isinstance(data, dict):
                    detail = data.get("detail") or data.get("error") or detail
            except Exception:
                detail = response.text or detail
            raise RuntimeError(f"Twitter API error: {response.status_code} - {detail}")
        return {} if response.status_code == 204 else response.json()

    async def follow_user(self, my_user_id: str, target_user_id: str) -> None:
        await self._request("POST", f"/users/{my_user_id}/following", json={"target_user_id": target_user_id})

    async def unfollow_user(self, my_user_id: str, target_user_id: str) -> None:
        await self._request("DELETE", f"/users/{my_user_id}/following/{target_user_id}")

    async def get_following(
        self,
        my_user_id: str,
        max_results: int = 100,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        params = {"max_results": str(max_results), "user.fields": "id,name,username,description,public_metrics,verified,profile_image_url"}
        if pagination_token:
            params["pagination_token"] = pagination_token
        return await self._request("GET", f"/users/{my_user_id}/following", params=params)

    async def get_followers(
        self,
        my_user_id: str,
        max_results: int = 100,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        params = {"max_results": str(max_results), "user.fields": "id,name,username,description,public_metrics,verified,profile_image_url"}
        if pagination_token:
            params["pagination_token"] = pagination_token
        return await self._request("GET", f"/users/{my_user_id}/followers", params=params)