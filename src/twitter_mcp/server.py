"""MCP server — Streamable HTTP JSON-RPC at /mcp.

The tool catalog lives in :mod:`twitter_mcp.api`; this module turns it into
MCP tool schemas, dispatches calls to the X API and serves the ASGI app that
both uvicorn (Docker / Zeabur) and Vercel use.
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .api import TOOLS, TOOL_INDEX, Tool
from .config import OAuth1Account, load_config
from .errors import OAuth2Unavailable, XApiError
from .oauth1 import TwitterClient
from .oauth2 import OAuth2Client

PROTOCOL_VERSION = "2025-03-26"
SERVER_NAME = "twitter-mcp-server"
SERVER_VERSION = "2.0.0"

# Where a user facing parameter is placed in the JSON body of the request.
# Anything not listed maps to a body field with the same name.
BODY_PATHS: dict[str, dict[str, tuple[str, ...]]] = {
    "post_tweet": {
        "in_reply_to_tweet_id": ("reply", "in_reply_to_tweet_id"),
        "media_ids": ("media", "media_ids"),
    },
    "reply_to_tweet": {
        "tweet_id": ("reply", "in_reply_to_tweet_id"),
        "media_ids": ("media", "media_ids"),
    },
    "follow_user": {"user_id": ("target_user_id",)},
    "block_user": {"user_id": ("target_user_id",)},
    "mute_user": {"user_id": ("target_user_id",)},
    "block_dms": {"user_id": ("target_user_id",)},
    "unblock_dms": {"user_id": ("target_user_id",)},
    "create_dm_conversation": {"media_ids": ("media", "media_ids")},
    "send_dm_by_participant": {"media_ids": ("media", "media_ids")},
    "send_dm_by_conversation": {"media_ids": ("media", "media_ids")},
    "create_media_subtitles": {"subtitles_base64": ("subtitles",)},
}

OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "json": {"type": "object", "additionalProperties": True},
    "tweet": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "text": {"type": "string"},
            "created_at": {"type": "string"},
        },
        "required": ["id"],
        "additionalProperties": True,
    },
    "tweet_list": {
        "type": "object",
        "properties": {
            "data": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "meta": {"type": "object", "additionalProperties": True},
            "includes": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": True,
    },
    "user": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "username": {"type": "string"},
            "name": {"type": "string"},
        },
        "required": ["id"],
        "additionalProperties": True,
    },
    "user_list": {
        "type": "object",
        "properties": {
            "data": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "meta": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": True,
    },
    "success": {
        "type": "object",
        "properties": {"success": {"type": "boolean"}},
        "required": ["success"],
        "additionalProperties": True,
    },
    "counts": {
        "type": "object",
        "properties": {
            "total": {"type": "integer"},
            "data": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        },
        "additionalProperties": True,
    },
    "media": {
        "type": "object",
        "properties": {
            "media_id": {"type": "string"},
            "media_key": {"type": "string"},
            "id": {"type": "string"},
        },
        "additionalProperties": True,
    },
}


# ---------------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------------


def input_schema(tool: Tool) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in tool.params:
        schema: dict[str, Any] = {"type": param.type}
        if param.description:
            schema["description"] = param.description
        if param.enum:
            schema["enum"] = list(param.enum)
        if param.minimum is not None:
            schema["minimum"] = param.minimum
        if param.maximum is not None:
            schema["maximum"] = param.maximum
        if param.default is not None:
            schema["default"] = param.default
        properties[param.name] = schema
        if param.required:
            required.append(param.name)
    schema_out: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema_out["required"] = required
    return schema_out


def tool_definition(tool: Tool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": input_schema(tool),
        "outputSchema": OUTPUT_SCHEMAS.get(tool.output, OUTPUT_SCHEMAS["json"]),
    }


# ---------------------------------------------------------------------------
# coverage reporting
# ---------------------------------------------------------------------------


def _normalise_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def coverage_report() -> dict[str, Any]:
    snapshot_path = Path(__file__).with_name("x_api_operations.json")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    operations = snapshot["operations"]

    curated = {
        (tool.method.upper(), _normalise_path(tool.path))
        for tool in TOOLS
        if tool.name != "x_api_request"
    }

    families: dict[str, dict[str, int]] = {}
    matched: list[dict[str, Any]] = []
    via_generic: list[dict[str, Any]] = []
    for operation in operations:
        key = (operation["method"], _normalise_path(operation["path"]))
        bucket = families.setdefault(operation["family"], {"total": 0, "curated": 0, "via_generic": 0})
        bucket["total"] += 1
        if key in curated:
            bucket["curated"] += 1
            matched.append(operation)
        else:
            bucket["via_generic"] += 1
            via_generic.append(operation)

    total = len(operations)
    return {
        "spec": {
            "title": snapshot.get("spec_title"),
            "version": snapshot.get("spec_version"),
            "source": snapshot.get("source"),
            "generated": snapshot.get("generated"),
        },
        "total_operations": total,
        "curated_operations": len(matched),
        "via_generic_tool": len(via_generic),
        "reachable_operations": total,
        "coverage_pct": round(100.0 * len(matched) / total, 1) if total else 0.0,
        "curated_tools": len([t for t in TOOLS if t.name != "x_api_request"]),
        "total_tools": len(TOOLS),
        "families": families,
        "curated_missing_examples": via_generic[:25],
    }


# ---------------------------------------------------------------------------
# tool runner
# ---------------------------------------------------------------------------


class ToolRunner:
    def __init__(self, client: TwitterClient, oauth2: OAuth2Client | None) -> None:
        self.client = client
        self.oauth2 = oauth2
        self.last_oauth2_error: str | None = None

    # -- transport selection ---------------------------------------------

    def _transports(self, tool: Tool) -> list[str]:
        oauth2_present = self.oauth2 is not None
        oauth2_usable = oauth2_present and self.oauth2 is not None and self.oauth2.available

        if tool.auth == "oauth2":
            if not oauth2_present:
                raise RuntimeError(
                    f"Tool '{tool.name}' needs OAuth 2.0 (scope: {', '.join(tool.scopes) or 'oauth2'}). "
                    "Set the TWITTER_OAUTH2_* environment variables."
                )
            if not oauth2_usable:
                reason = self.oauth2.disabled_reason if self.oauth2 else "unavailable"
                raise RuntimeError(
                    f"OAuth 2.0 is configured but unusable: {reason}. "
                    "Re-authorize with scripts/oauth2_bootstrap.py and update TWITTER_OAUTH2_ACCESS_TOKEN and "
                    "TWITTER_OAUTH2_REFRESH_TOKEN."
                )
            return ["oauth2"]
        if tool.auth == "auto":
            return ["oauth2", "oauth1"] if oauth2_usable else ["oauth1"]

        # Reads work on OAuth 1.0a, but X rejects writes on that transport for
        # projects that use OAuth 2.0, so writes try OAuth 2.0 first.
        if tool.method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            return ["oauth2", "oauth1"] if oauth2_usable else ["oauth1"]
        return ["oauth1", "oauth2"] if oauth2_usable else ["oauth1"]

    async def _dispatch(self, transports: list[str], method: str, path: str, **kwargs: Any) -> Any:
        failures: list[str] = []
        last_error: XApiError | None = None
        for index, transport in enumerate(transports):
            try:
                if transport == "oauth1":
                    return await self.client.request(method, path, **kwargs)
                assert self.oauth2 is not None
                return await self.oauth2.request(method, path, **kwargs)
            except OAuth2Unavailable as exc:
                failures.append(f"{transport}: {exc}")
                self._note_oauth2_unusable(exc)
                continue
            except XApiError as exc:
                last_error = exc
                failures.append(f"{transport}: {exc}")
                if index == len(transports) - 1:
                    break
                if exc.status_code not in (400, 401, 403):
                    raise
        if last_error is not None:
            if len(failures) > 1:
                last_error.detail = f"{last_error.detail} | attempts: {', '.join(failures)}"
            raise last_error
        raise RuntimeError("; ".join(failures) or "no transport available")

    def _note_oauth2_unusable(self, exc: OAuth2Unavailable) -> None:
        """Remember that OAuth 2.0 failed so diagnostics can report it."""
        if self.oauth2 is not None and self.oauth2.available:
            self.oauth2.disabled_reason = str(exc)
        self.last_oauth2_error = str(exc)

    async def diagnostics(self) -> dict[str, Any]:
        """Runtime proof of the credential and transport state."""
        state: dict[str, Any] = {
            "oauth1": {
                "configured": bool(self.client.account.api_key),
                "account": self.client.name,
            },
            "oauth2": {
                "configured": self.oauth2 is not None,
                "usable": bool(self.oauth2 is not None and self.oauth2.available),
                "reason": self.oauth2.disabled_reason if self.oauth2 else "not configured",
                "scope": self.oauth2._tokens.scope if self.oauth2 else None,
            },
            "last_oauth2_error": self.last_oauth2_error,
        }
        probes: dict[str, Any] = {}
        try:
            me = await self.client.request("GET", "/2/users/me", params={"user.fields": "id,username,name"})
            probes["oauth1_get_users_me"] = {"ok": True, "data": me.get("data")}
        except Exception as exc:  # noqa: BLE001
            probes["oauth1_get_users_me"] = {"ok": False, "error": str(exc)}
        if self.oauth2 is not None:
            try:
                me2 = await self.oauth2.request("GET", "/2/users/me", params={"user.fields": "id,username,name"})
                probes["oauth2_get_users_me"] = {"ok": True, "data": me2.get("data")}
            except Exception as exc:  # noqa: BLE001
                probes["oauth2_get_users_me"] = {"ok": False, "error": str(exc)}
        state["probes"] = probes
        state["posts"] = {
            "endpoint": "POST /2/tweets",
            "note": "publishing needs Read and write permissions, an active credit balance and a token with "
            "tweet.write; the server cannot verify the developer portal settings",
        }
        return state

    # -- parameter preparation -------------------------------------------

    async def _prepare(self, tool: Tool, args: dict[str, Any]) -> dict[str, Any]:
        query: dict[str, Any] = {}
        body: dict[str, Any] = {}
        files: dict[str, Any] | None = None
        data: dict[str, Any] | None = None
        path = tool.path
        overrides = BODY_PATHS.get(tool.name, {})
        path_params = set(tool.path_params)
        excluded_from_query = path_params | set(tool.query_exclude)

        for param in tool.params:
            if param.name in excluded_from_query:
                continue
            value = args.get(param.name)
            if value is None and param.default is not None:
                value = param.default
            if value is None:
                continue
            if param.name == "payload" and isinstance(value, dict):
                body.update(value)
                continue
            target = overrides.get(param.name, (param.name,))
            if target[0] in tool.body_params:
                _assign(body, target, value)
            else:
                query[param.api_name or param.name] = value

        # username alias -> user id (resolved before the path is assembled)
        alias_user_id: str | None = None
        if tool.name == "get_user_tweets" and not args.get("user_id") and args.get("username"):
            user = await self.client.get_user_by_username(str(args["username"]))
            alias_user_id = str(user["id"])
            path = path.replace("{user_id}", quote(alias_user_id, safe=""))

        # path parameters
        for name in tool.path_params:
            if name == "me":
                me = await self.client.get_me()
                path = path.replace("{me}", quote(str(me["id"]), safe=""))
                continue
            if name == "user_id" and alias_user_id is not None:
                continue
            value = args.get(name)
            if value is None:
                param = next((p for p in tool.params if p.name == name), None)
                value = param.default if param is not None else None
            if value is None:
                raise ValueError(f"Missing required path parameter: {name}")
            path = path.replace("{" + name + "}", quote(str(value), safe=""))

        # multipart uploads
        if tool.name == "upload_media":
            payload = base64.b64decode(str(args["media_base64"]))
            files = {"media": (args.get("filename") or "upload.png", payload, args.get("media_type") or "image/png")}
            data = {"media_category": args.get("media_category") or "tweet_image"}
            if args.get("additional_owners"):
                data["additional_owners"] = json.dumps(args["additional_owners"])
        elif tool.name == "upload_compliance_submission" and args.get("file_base64"):
            payload = base64.b64decode(str(args["file_base64"]))
            files = {"file": (args.get("file_name") or "ids.txt", payload, "text/plain")}

        return {"path": path, "query": query, "body": body or None, "files": files, "data": data}

    # -- raw passthrough --------------------------------------------------

    async def _raw(self, args: dict[str, Any]) -> Any:
        method = str(args.get("method", "GET")).upper()
        path = str(args.get("path", "")).strip()
        if not path.startswith("/") or "://" in path or path.startswith("//"):
            raise ValueError("path must be a relative path, for example /2/users/123/liked_tweets")
        if not re.match(r"^/(2|1\.1|oauth2)/", path):
            raise ValueError("path must start with /2/, /1.1/ or /oauth2/")
        query = args.get("query") or {}
        body = args.get("body")
        if not isinstance(query, dict):
            raise ValueError("query must be an object")
        if body is not None and not isinstance(body, dict):
            raise ValueError("body must be an object")

        choice = str(args.get("auth") or "auto")
        oauth2_usable = self.oauth2 is not None and self.oauth2.available
        if choice == "oauth2":
            if self.oauth2 is None:
                raise RuntimeError("OAuth 2.0 is not configured on this server")
            if not oauth2_usable:
                raise RuntimeError(f"OAuth 2.0 is configured but unusable: {self.oauth2.disabled_reason}")
            transports = ["oauth2"]
        elif choice == "oauth1":
            transports = ["oauth1"]
        else:
            transports = ["oauth2", "oauth1"] if oauth2_usable else ["oauth1"]
        return await self._dispatch(transports, method, path, params=query, json_body=body)

    # -- entry point ------------------------------------------------------

    async def run(self, tool: Tool, args: dict[str, Any]) -> Any:
        if tool.name == "x_api_request":
            return await self._raw(args)
        prepared = await self._prepare(tool, args)
        transports = self._transports(tool)
        return await self._dispatch(
            transports,
            tool.method,
            prepared["path"],
            params=prepared["query"],
            json_body=prepared["body"],
            files=prepared["files"],
            data=prepared["data"],
        )


def _assign(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cursor = target
    for key in path[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[path[-1]] = value


# ---------------------------------------------------------------------------
# application
# ---------------------------------------------------------------------------


def create_app(client: TwitterClient | None = None, oauth2: OAuth2Client | None = None) -> Starlette:
    if client is None:
        try:
            account = load_config().account
        except Exception:
            account = OAuth1Account(
                name=os.getenv("ACCOUNT_NAME") or "Twitter Account",
                api_key=os.getenv("TWITTER_API_KEY") or "",
                api_secret=os.getenv("TWITTER_API_SECRET") or "",
                access_token=os.getenv("TWITTER_ACCESS_TOKEN") or "",
                access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET") or "",
            )
        client = TwitterClient(account)
    if oauth2 is None:
        oauth2 = OAuth2Client.from_env()

    runner = ToolRunner(client, oauth2)
    schemas = [tool_definition(tool) for tool in TOOLS]

    def _route_of(path: str) -> str:
        if path.endswith("/mcp"):
            return "mcp"
        if path.endswith("/health"):
            return "health"
        if path.endswith("/diagnostics"):
            return "diagnostics"
        if path.endswith("/tools-manifest.json"):
            return "manifest"
        if path.endswith("/api-coverage"):
            return "coverage"
        return "root"

    async def endpoint(request: Request) -> Response:
        route = _route_of(request.url.path)
        is_post = request.method == "POST"

        if is_post:
            # Any POST that carries a JSON-RPC envelope is treated as MCP so the
            # server works behind rewrites that collapse the path (Vercel).
            try:
                probe = await request.json()
            except Exception:
                probe = None
            if isinstance(probe, dict) and "method" in probe:
                route = "mcp"

        if not is_post:
            query = request.query_params
            if "health" in query:
                route = "health"
            elif "manifest" in query:
                route = "manifest"
            elif "coverage" in query:
                route = "coverage"

        if route == "health":
            return JSONResponse(
                {
                    "status": "healthy",
                    "account": client.name,
                    "oauth1": "configured" if client.account.api_key else "missing",
                    "oauth2": "configured" if oauth2 is not None else "disabled",
                    "tools": len(TOOLS),
                }
            )

        if route == "manifest":
            return JSONResponse({"server": SERVER_NAME, "version": SERVER_VERSION, "tools": schemas})

        if route == "diagnostics":
            return JSONResponse(await runner.diagnostics())

        if route == "coverage":
            return JSONResponse(coverage_report())

        if route == "root":
            return JSONResponse(
                {
                    "name": "Twitter MCP Server",
                    "version": SERVER_VERSION,
                    "description": "MCP server for the X API v2 (OAuth 1.0a + optional OAuth 2.0)",
                    "account": client.name,
                    "oauth2": "configured" if oauth2 is not None else "disabled",
                    "tools": len(TOOLS),
                    "endpoints": {
                        "health": "/health",
                        "mcp": "/mcp",
                        "manifest": "/tools-manifest.json",
                        "coverage": "/api-coverage",
                        "diagnostics": "/diagnostics",
                    },
                }
            )

        # MCP JSON-RPC
        if request.method == "DELETE":
            return Response(status_code=204)
        if request.method != "POST":
            return JSONResponse(
                {"error": "Use POST for MCP JSON-RPC requests"},
                status_code=405,
                headers={"Allow": "POST, DELETE"},
            )
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}},
                status_code=400,
            )

        method = body.get("method")
        request_id = body.get("id")

        if request_id is None:
            # notification - no response body
            return Response(status_code=202)

        if method == "initialize":
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    },
                }
            )
        if method == "ping":
            return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": {}})
        if method == "tools/list":
            return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": {"tools": schemas}})
        if method == "resources/list":
            return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": {"resources": []}})
        if method == "prompts/list":
            return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": {"prompts": []}})
        if method == "tools/call":
            params = body.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            tool = TOOL_INDEX.get(name)
            if tool is None:
                return JSONResponse(
                    {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}
                )
            try:
                payload = await runner.run(tool, arguments)
            except Exception as exc:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                            "isError": True,
                        },
                    }
                )
            if payload is None:
                payload = {"success": True}
            elif isinstance(payload, dict) and not payload:
                payload = {"success": True}
            text = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=False, default=str)
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": text}],
                        "structuredContent": payload if isinstance(payload, dict) else {"result": payload},
                    },
                }
            )
        return JSONResponse(
            {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        )

    app = Starlette(
        routes=[Route("/{path:path}", endpoint, methods=["GET", "POST", "DELETE", "OPTIONS"])],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ],
    )
    app.state.client = client
    app.state.oauth2 = oauth2
    app.state.runner = runner
    return app


app = create_app()


def main() -> None:
    cfg = load_config()
    application = create_app()
    print(
        f"[mcp] Twitter MCP Server listening on http://{cfg.host}:{cfg.port}/mcp "
        f"(account={cfg.account.name}, tools={len(TOOLS)})",
        flush=True,
    )
    uvicorn.run(application, host=cfg.host, port=cfg.port, log_level="warning")


if __name__ == "__main__":
    main()
