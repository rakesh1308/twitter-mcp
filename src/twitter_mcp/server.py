"""MCP server — Streamable HTTP at /mcp, plus / and /health."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Callable

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .config import load_config
from .oauth1 import TwitterClient
from .oauth2 import OAuth2Client

API_VERSION = "2025-03-26"


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def build_handlers(client: TwitterClient, oauth2: OAuth2Client | None) -> dict[str, Callable[..., Any]]:
    handlers: dict[str, Callable[..., Any]] = {}

    def _text(payload: Any) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": _json(payload)}]}

    def _err(message: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps({"error": message})}], "isError": True}

    def post_tweet(text: str) -> dict[str, Any]:
        return _text(client.post_tweet(text))

    def reply_to_tweet(tweet_id: str, text: str) -> dict[str, Any]:
        return _text(client.reply_to_tweet(tweet_id, text))

    def get_tweet(tweet_id: str) -> dict[str, Any]:
        return _text(client.get_tweet(tweet_id))

    def search_tweets(query: str, max_results: int = 10) -> dict[str, Any]:
        return _text(client.search_tweets(query, max_results))

    def search_all_tweets(query: str, max_results: int = 10) -> dict[str, Any]:
        return _text(client.search_all_tweets(query, max_results))

    def get_user(username: str) -> dict[str, Any]:
        return _text(client.get_user_by_username(username))

    def get_user_tweets(username: str, max_results: int = 10) -> dict[str, Any]:
        user = client.get_user_by_username(username)
        return _text(client.get_user_tweets(user["id"], max_results))

    def retweet(tweet_id: str, user_id: str) -> dict[str, Any]:
        client.retweet(tweet_id, user_id)
        return _text({"success": True, "message": f"Retweeted {tweet_id}"})

    def like_tweet(tweet_id: str, user_id: str) -> dict[str, Any]:
        client.like_tweet(tweet_id, user_id)
        return _text({"success": True, "message": f"Liked {tweet_id}"})

    def delete_tweet(tweet_id: str) -> dict[str, Any]:
        client.delete_tweet(tweet_id)
        return _text({"success": True, "message": f"Deleted {tweet_id}"})

    def list_accounts() -> dict[str, Any]:
        return _text({"account": client.name})

    handlers.update(
        post_tweet=post_tweet,
        reply_to_tweet=reply_to_tweet,
        get_tweet=get_tweet,
        search_tweets=search_tweets,
        search_all_tweets=search_all_tweets,
        get_user=get_user,
        get_user_tweets=get_user_tweets,
        retweet=retweet,
        like_tweet=like_tweet,
        delete_tweet=delete_tweet,
        list_accounts=list_accounts,
    )

    if oauth2 is not None:
        def follow_user(user_id: str) -> dict[str, Any]:
            assert oauth2 is not None
            me = client.get_me()
            asyncio.run(oauth2.follow_user(me["id"], user_id))
            return _text({"success": True, "followed": user_id})

        def unfollow_user(user_id: str) -> dict[str, Any]:
            assert oauth2 is not None
            me = client.get_me()
            asyncio.run(oauth2.unfollow_user(me["id"], user_id))
            return _text({"success": True, "unfollowed": user_id})

        def get_following(max_results: int = 100, pagination_token: str | None = None) -> dict[str, Any]:
            assert oauth2 is not None
            me = client.get_me()
            res = asyncio.run(oauth2.get_following(me["id"], max_results, pagination_token))
            return _text({
                "count": len(res.get("data") or []),
                "next_token": (res.get("meta") or {}).get("next_token"),
                "users": res.get("data") or [],
            })

        def get_followers(max_results: int = 100, pagination_token: str | None = None) -> dict[str, Any]:
            assert oauth2 is not None
            me = client.get_me()
            res = asyncio.run(oauth2.get_followers(me["id"], max_results, pagination_token))
            return _text({
                "count": len(res.get("data") or []),
                "next_token": (res.get("meta") or {}).get("next_token"),
                "users": res.get("data") or [],
            })

        handlers.update(
            follow_user=follow_user,
            unfollow_user=unfollow_user,
            get_following=get_following,
            get_followers=get_followers,
        )

    return handlers


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"name": "post_tweet", "description": "Post a new tweet. text: tweet text (max 280 chars).", "params": {"text": "string"}, "required": ["text"]},
    {"name": "reply_to_tweet", "description": "Reply to a tweet. tweet_id, text.", "params": {"tweet_id": "string", "text": "string"}, "required": ["tweet_id", "text"]},
    {"name": "get_tweet", "description": "Get tweet details. tweet_id.", "params": {"tweet_id": "string"}, "required": ["tweet_id"]},
    {"name": "search_tweets", "description": "Search recent tweets. query, max_results (1-100, default 10).", "params": {"query": "string", "max_results": "int"}, "required": ["query"]},
    {"name": "search_all_tweets", "description": "Search all tweets (elevated API). query, max_results (1-100, default 10).", "params": {"query": "string", "max_results": "int"}, "required": ["query"]},
    {"name": "get_user", "description": "Get user info by username. username (no @).", "params": {"username": "string"}, "required": ["username"]},
    {"name": "get_user_tweets", "description": "Get recent tweets from a user. username, max_results (1-100, default 10).", "params": {"username": "string", "max_results": "int"}, "required": ["username"]},
    {"name": "retweet", "description": "Retweet a tweet. tweet_id, user_id (your numeric ID).", "params": {"tweet_id": "string", "user_id": "string"}, "required": ["tweet_id", "user_id"]},
    {"name": "like_tweet", "description": "Like a tweet. tweet_id, user_id.", "params": {"tweet_id": "string", "user_id": "string"}, "required": ["tweet_id", "user_id"]},
    {"name": "delete_tweet", "description": "Delete one of your tweets. tweet_id.", "params": {"tweet_id": "string"}, "required": ["tweet_id"]},
    {"name": "list_accounts", "description": "Show configured account.", "params": {}, "required": []},
    {"name": "follow_user", "description": "Follow a user (OAuth 2.0). user_id.", "params": {"user_id": "string"}, "required": ["user_id"], "oauth2": True},
    {"name": "unfollow_user", "description": "Unfollow a user (OAuth 2.0). user_id.", "params": {"user_id": "string"}, "required": ["user_id"], "oauth2": True},
    {"name": "get_following", "description": "List accounts you follow (OAuth 2.0). max_results, pagination_token.", "params": {"max_results": "int", "pagination_token": "string"}, "required": [], "oauth2": True},
    {"name": "get_followers", "description": "List accounts following you (OAuth 2.0). max_results, pagination_token.", "params": {"max_results": "int", "pagination_token": "string"}, "required": [], "oauth2": True},
]


def tool_schemas(include_oauth2: bool) -> list[dict[str, Any]]:
    return [t for t in TOOL_SCHEMAS if include_oauth2 or not t.get("oauth2")]


def main() -> None:
    cfg = load_config()
    client = TwitterClient(cfg.account)
    oauth2 = OAuth2Client.from_env()
    handlers = build_handlers(client, oauth2)
    schemas = tool_schemas(oauth2 is not None)
    host = cfg.host
    port = cfg.port

    async def mcp_endpoint(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}})
        method = body.get("method")
        rid = body.get("id")
        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": API_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "twitter-mcp-server", "version": "1.0.0"},
                },
            })
        if method == "tools/list":
            tools = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": {
                        "type": "object",
                        "properties": {k: {"type": "string" if v == "string" else "number"} for k, v in t["params"].items()},
                        **({"required": t["required"]} if t["required"] else {}),
                    },
                }
                for t in schemas
            ]
            return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}})
        if method == "tools/call":
            params = body.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            handler = handlers.get(name)
            if handler is None:
                return JSONResponse({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Unknown tool: {name}"}})
            try:
                result = handler(**args)
                return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": result})
            except Exception as exc:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                        "isError": True,
                    },
                })
        if method == "ping":
            return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {}})
        return JSONResponse({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}})

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({
            "status": "healthy",
            "account": client.name,
            "oauth2": "configured" if oauth2 is not None else "disabled",
        })

    async def root(_request: Request) -> JSONResponse:
        return JSONResponse({
            "name": "Twitter MCP Server",
            "version": "1.0.0",
            "description": "MCP server for Twitter API v2 (OAuth 1.0a + optional OAuth 2.0)",
            "account": client.name,
            "oauth2": "configured" if oauth2 is not None else "disabled",
            "endpoints": {"health": "/health", "mcp": "/mcp"},
        })

    app = Starlette(routes=[
        Route("/", root, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Route("/mcp", mcp_endpoint, methods=["POST", "GET", "DELETE"]),
    ])

    print(f"[mcp] Twitter MCP Server listening on http://{host}:{port}/mcp (account={client.name}, oauth2={'on' if oauth2 else 'off'})", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()