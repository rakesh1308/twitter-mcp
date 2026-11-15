"""Contract tests for the MCP tool catalog."""

from __future__ import annotations

import asyncio

from twitter_mcp.api import TOOLS, TOOL_INDEX
from twitter_mcp.oauth1 import TwitterClient
from twitter_mcp.server import ToolRunner, create_app, input_schema

VALID_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


def test_tool_names_are_unique_and_snake_case() -> None:
    assert len(TOOL_INDEX) == len(TOOLS)
    for tool in TOOLS:
        assert tool.name == tool.name.lower()
        assert tool.name.replace("_", "").isalnum()


def test_every_tool_targets_the_v2_namespace() -> None:
    for tool in TOOLS:
        assert tool.path.startswith("/2/"), tool.name


def test_input_schemas_are_valid() -> None:
    for tool in TOOLS:
        schema = input_schema(tool)
        assert schema["type"] == "object"
        for name, prop in schema["properties"].items():
            assert prop["type"] in VALID_TYPES, f"{tool.name}.{name}"
            assert isinstance(prop.get("description", ""), str)


def test_path_parameters_are_resolvable() -> None:
    for tool in TOOLS:
        param_names = {p.name for p in tool.params}
        for path_param in tool.path_params:
            assert path_param == "me" or path_param in param_names, f"{tool.name}.{path_param}"


def test_generic_escape_hatch_exists() -> None:
    assert "x_api_request" in TOOL_INDEX
    tool = TOOL_INDEX["x_api_request"]
    assert tool.auth == "auto"


def test_read_tools_accept_pagination() -> None:
    for name in ("search_tweets", "get_user_tweets", "get_following", "get_followers"):
        params = {p.name for p in TOOL_INDEX[name].params}
        assert "pagination_token" in params, name


def test_search_query_is_not_string_interpolated() -> None:
    """Regression: ampersand and hash in a query must reach the API intact."""
    runner = ToolRunner(client=None, oauth2=None)  # type: ignore[arg-type]
    tool = TOOL_INDEX["search_tweets"]
    prepared = asyncio.run(runner._prepare(tool, {"query": "cats & dogs #tag", "max_results": 5}))
    assert prepared["query"]["query"] == "cats & dogs #tag"


def test_app_serves_tool_list() -> None:
    from starlette.testclient import TestClient

    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert response.status_code == 200
        tools = response.json()["result"]["tools"]
        assert len(tools) == len(TOOLS)
        assert {t["name"] for t in tools} == set(TOOL_INDEX)


def test_health_and_coverage_endpoints() -> None:
    from starlette.testclient import TestClient

    app = create_app()
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        coverage = client.get("/api-coverage")
        assert coverage.status_code == 200
        payload = coverage.json()
        assert payload["total_operations"] == 260
        assert payload["reachable_operations"] == 260
        assert payload["curated_operations"] >= 150


def test_search_query_url_is_correctly_encoded_end_to_end() -> None:
    """The raw query must reach the API encoded, not truncated at & or #."""
    import httpx
    from authlib.integrations.httpx_client import OAuth1Auth

    from twitter_mcp.config import OAuth1Account

    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"data": []})

    account = OAuth1Account(name="t", api_key="k", api_secret="s", access_token="t", access_token_secret="s")

    async def scenario() -> None:
        client = TwitterClient(account)
        await client._client.aclose()
        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
            auth=OAuth1Auth(client_id="k", client_secret="s", token="t", token_secret="s"),
        )
        runner = ToolRunner(client=client, oauth2=None)
        await runner.run(TOOL_INDEX["search_tweets"], {"query": "cats & dogs #tag", "max_results": 5})
        await client.aclose()

    asyncio.run(scenario())
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(captured["url"])
    assert parse_qs(parsed.query)["query"] == ["cats & dogs #tag"], captured["url"]
    assert "%26" in captured["url"] and "%23" in captured["url"], captured["url"]

def test_path_parameters_are_not_duplicated_in_the_query_string() -> None:
    """Regression: a path parameter must not be sent again as a query parameter."""
    runner = ToolRunner(client=None, oauth2=None)  # type: ignore[arg-type]

    prepared = asyncio.run(runner._prepare(TOOL_INDEX["get_tweet"], {"tweet_id": "123"}))
    assert prepared["path"] == "/2/tweets/123"
    assert "tweet_id" not in prepared["query"]

    prepared = asyncio.run(runner._prepare(TOOL_INDEX["get_user"], {"username": "xdevelopers"}))
    assert prepared["path"] == "/2/users/by/username/xdevelopers"
    assert "username" not in prepared["query"]

    prepared = asyncio.run(runner._prepare(TOOL_INDEX["remove_list_member"], {"list_id": "9", "user_id": "7"}))
    assert prepared["path"] == "/2/lists/9/members/7"
    assert "list_id" not in prepared["query"] and "user_id" not in prepared["query"]


class _StubClient:
    async def get_user_by_username(self, username: str) -> dict:
        return {"id": "42", "username": username}

    async def get_me(self) -> dict:
        return {"id": "99"}


def test_username_alias_is_not_sent_as_query_parameter() -> None:
    runner = ToolRunner(client=_StubClient(), oauth2=None)  # type: ignore[arg-type]
    prepared = asyncio.run(runner._prepare(TOOL_INDEX["get_user_tweets"], {"username": "xdevelopers"}))
    assert "username" not in prepared["query"]
    assert prepared["path"] == "/2/users/42/tweets"

def test_max_results_bounds_match_the_x_api() -> None:
    """X rejects page sizes below 10 on search and user post listings."""
    for name in ("search_tweets", "search_all_tweets", "get_user_tweets", "get_user_mentions", "get_liked_tweets"):
        schema = input_schema(TOOL_INDEX[name])
        assert schema["properties"]["max_results"]["minimum"] == 10, name
        assert schema["properties"]["max_results"]["maximum"] == 100, name

    for name in ("get_following", "get_followers"):
        schema = input_schema(TOOL_INDEX[name])
        assert schema["properties"]["max_results"]["minimum"] == 1, name
        assert schema["properties"]["max_results"]["maximum"] == 1000, name

class _StubOAuth2:
    def __init__(self, available: bool = True, reason: str = "") -> None:
        self.available = available
        self.disabled_reason = reason

    async def request(self, *args: object, **kwargs: object) -> dict:
        raise AssertionError("should not be called")


def test_write_tools_prefer_oauth2_and_reads_prefer_oauth1() -> None:
    runner = ToolRunner(client=None, oauth2=_StubOAuth2(available=True))  # type: ignore[arg-type]
    assert runner._transports(TOOL_INDEX["post_tweet"]) == ["oauth2", "oauth1"]
    assert runner._transports(TOOL_INDEX["get_user"]) == ["oauth1", "oauth2"]
    assert runner._transports(TOOL_INDEX["x_api_request"]) == ["oauth2", "oauth1"]


def test_broken_oauth2_is_skipped_and_reported() -> None:
    broken = _StubOAuth2(available=False, reason="X rejected the OAuth 2.0 refresh token")
    runner = ToolRunner(client=None, oauth2=broken)  # type: ignore[arg-type]
    assert runner._transports(TOOL_INDEX["post_tweet"]) == ["oauth1"]
    assert runner._transports(TOOL_INDEX["x_api_request"]) == ["oauth1"]
    try:
        runner._transports(TOOL_INDEX["upload_media"])
    except RuntimeError as exc:
        assert "rejected the OAuth 2.0 refresh token" in str(exc)
    else:
        raise AssertionError("expected a RuntimeError for an unusable OAuth 2.0 client")


def test_dispatch_falls_back_to_oauth1_when_oauth2_is_unavailable() -> None:
    class BrokenOAuth2(_StubOAuth2):
        async def request(self, *args: object, **kwargs: object) -> dict:
            from twitter_mcp.errors import OAuth2Unavailable

            raise OAuth2Unavailable("refresh token rejected")

    class WorkingOAuth1:
        async def request(self, *args: object, **kwargs: object) -> dict:
            return {"data": [{"id": "1"}]}

    runner = ToolRunner(client=WorkingOAuth1(), oauth2=BrokenOAuth2())  # type: ignore[arg-type]
    result = asyncio.run(runner._dispatch(["oauth2", "oauth1"], "GET", "/2/users/me"))
    assert result == {"data": [{"id": "1"}]}


def test_post_errors_carry_actionable_hints() -> None:
    from twitter_mcp.errors import XApiError

    error = XApiError(400, "Invalid Request", "POST", "/2/tweets")
    assert "Read and write permissions" in str(error)
    assert "credit balance" in str(error)
    assert "POST /2/tweets" in str(error)

def test_unknown_oauth2_expiry_uses_the_access_token_first() -> None:
    """A bootstrap token must be used as it is; refresh only happens on a 401."""
    import time as _time

    from twitter_mcp.oauth2 import OAuth2Client, OAuth2Options, OAuth2Tokens, _parse_expires

    assert _parse_expires(None) == 0
    assert _parse_expires("not-a-date") == 0

    unknown = OAuth2Tokens(client_id="c", client_secret="s", access_token="a", refresh_token="r", expires_at=0)
    assert OAuth2Client(unknown, OAuth2Options())._is_expired() is False

    expired = OAuth2Tokens(
        client_id="c",
        client_secret="s",
        access_token="a",
        refresh_token="r",
        expires_at=int(_time.time()) - 10,
    )
    assert OAuth2Client(expired, OAuth2Options())._is_expired() is True