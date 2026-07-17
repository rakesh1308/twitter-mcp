"""OAuth 1.0a Twitter API v2 client."""

from __future__ import annotations

from typing import Any

import httpx
from authlib.integrations.httpx_client import OAuth1Auth

from .config import OAuth1Account

API_BASE = "https://api.twitter.com/2"
DEFAULT_PAGE_SIZE = 10


class TwitterClient:
    def __init__(self, account: OAuth1Account) -> None:
        self.account = account
        self._client = httpx.Client(
            base_url=API_BASE,
            auth=OAuth1Auth(
                client_id=account.api_key,
                client_secret=account.api_secret,
                token=account.access_token,
                token_secret=account.access_token_secret,
            ),
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TwitterClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @property
    def name(self) -> str:
        return self.account.name

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path, **kwargs)
        if not response.is_success and response.status_code != 204:
            self._raise(response)
        return {} if response.status_code == 204 else response.json()

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        detail = response.reason_phrase
        try:
            data = response.json()
            if isinstance(data, dict):
                detail = data.get("detail") or data.get("error") or detail
        except Exception:
            detail = response.text or detail
        raise RuntimeError(f"Twitter API error: {response.status_code} - {detail}")

    # ---- tweet lifecycle -------------------------------------------------

    def post_tweet(self, text: str) -> dict[str, Any]:
        return self._request("POST", "/tweets", json={"text": text})["data"]

    def reply_to_tweet(self, tweet_id: str, text: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/tweets",
            json={"text": text, "reply": {"in_reply_to_tweet_id": tweet_id}},
        )["data"]

    def delete_tweet(self, tweet_id: str) -> None:
        self._request("DELETE", f"/tweets/{tweet_id}")

    def retweet(self, tweet_id: str, user_id: str) -> None:
        self._request("POST", f"/users/{user_id}/retweets", json={"tweet_id": tweet_id})

    def like_tweet(self, tweet_id: str, user_id: str) -> None:
        self._request("POST", f"/users/{user_id}/likes", json={"tweet_id": tweet_id})

    # ---- reads ------------------------------------------------------------

    def get_tweet(self, tweet_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/tweets/{tweet_id}?expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url",
        )["data"]

    def search_tweets(self, query: str, max_results: int = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/tweets/search/recent?query={query}&max_results={max_results}&expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url",
        )

    def search_all_tweets(self, query: str, max_results: int = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/tweets/search/all?query={query}&max_results={max_results}&expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url",
        )

    def get_user_by_username(self, username: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/users/by/username/{username}?user.fields=created_at,description,public_metrics,profile_image_url,verified,url",
        )["data"]

    def get_me(self) -> dict[str, Any]:
        return self._request("GET", "/users/me?user.fields=id,username,name,created_at")["data"]

    def get_user_tweets(
        self,
        user_id: str,
        max_results: int = 100,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        params = [f"max_results={max_results}"]
        if pagination_token:
            params.append(f"pagination_token={pagination_token}")
        return self._request("GET", f"/users/{user_id}/tweets?{'&'.join(params)}")