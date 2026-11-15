"""OAuth 1.0a Twitter API v2 client (async).

All request parameters are passed to httpx as structured values, so query
strings and path segments are percent-encoded by the HTTP layer instead of
being interpolated by hand.
"""

from __future__ import annotations

from typing import Any

import httpx
from authlib.integrations.httpx_client import OAuth1Auth

from .config import OAuth1Account
from .errors import XApiError, _describe_error

API_BASE = "https://api.x.com"
DEFAULT_PAGE_SIZE = 10


class TwitterClient:
    def __init__(
        self,
        account: OAuth1Account,
        base_url: str = API_BASE,
        timeout: float = 30.0,
    ) -> None:
        self.account = account
        self.base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=OAuth1Auth(
                client_id=account.api_key,
                client_secret=account.api_secret,
                token=account.access_token,
                token_secret=account.access_token_secret,
            ),
            timeout=timeout,
        )
        self._me: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return self.account.name

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self._client.request(
            method,
            path,
            params=params,
            json=json_body,
            files=files,
            data=data,
            headers=headers,
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

    # ---- identity ---------------------------------------------------------

    async def get_me(self) -> dict[str, Any]:
        if self._me is None:
            payload = await self.request(
                "GET",
                "/2/users/me",
                params={"user.fields": "id,username,name,created_at"},
            )
            self._me = payload["data"]
        return self._me

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        payload = await self.request(
            "GET",
            f"/2/users/by/username/{username}",
            params={"user.fields": "created_at,description,public_metrics,profile_image_url,verified,url"},
        )
        return payload["data"]

    # ---- lifecycle helpers kept for library users -------------------------

    async def post_tweet(self, text: str, in_reply_to_tweet_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"text": text}
        if in_reply_to_tweet_id:
            body["reply"] = {"in_reply_to_tweet_id": in_reply_to_tweet_id}
        payload = await self.request("POST", "/2/tweets", json_body=body)
        return payload["data"]

    async def reply_to_tweet(self, tweet_id: str, text: str) -> dict[str, Any]:
        return await self.post_tweet(text, in_reply_to_tweet_id=tweet_id)

    async def delete_tweet(self, tweet_id: str) -> None:
        await self.request("DELETE", f"/2/tweets/{tweet_id}")

    async def retweet(self, tweet_id: str, user_id: str) -> None:
        await self.request("POST", f"/2/users/{user_id}/retweets", json_body={"tweet_id": tweet_id})

    async def like_tweet(self, tweet_id: str, user_id: str) -> None:
        await self.request("POST", f"/2/users/{user_id}/likes", json_body={"tweet_id": tweet_id})
