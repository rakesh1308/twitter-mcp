"""Environment-driven typed config."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OAuth1Account:
    name: str
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str


@dataclass(frozen=True)
class Config:
    account: OAuth1Account
    host: str
    port: int


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def load_config() -> Config:
    return Config(
        account=OAuth1Account(
            name=os.getenv("ACCOUNT_NAME") or "Twitter Account",
            api_key=_require("TWITTER_API_KEY"),
            api_secret=_require("TWITTER_API_SECRET"),
            access_token=_require("TWITTER_ACCESS_TOKEN"),
            access_token_secret=_require("TWITTER_ACCESS_TOKEN_SECRET"),
        ),
        host=os.getenv("HOST") or "0.0.0.0",
        port=int(os.getenv("PORT") or "3000"),
    )