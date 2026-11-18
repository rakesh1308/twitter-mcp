"""Contract tests for the MCP tool catalog."""

from __future__ import annotations

import asyncio

from twitter_mcp.api import TOOLS, TOOL_INDEX
from twitter_mcp.oauth1 import TwitterClient
from twitter_mcp.server import ToolRunner, create_app, input_schema, tool_definition

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
            if prop["type"] == "array":
                assert prop["items"]["type"] in {"string", "object"}, f"{tool.name}.{name}"


def test_output_schemas_match_x_response_envelopes() -> None:
    for name in ("get_me", "get_user", "get_tweet", "post_tweet"):
        schema = tool_definition(TOOL_INDEX[name])["outputSchema"]
        assert "data" in schema["properties"]
        assert "data" in schema["required"]
        assert "id" not in schema.get("required", [])

    success = tool_definition(TOOL_INDEX["add_list_member"])["outputSchema"]
    assert "success" not in success.get("required", [])


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


def test_query_arrays_are_comma_separated() -> None:
    runner = ToolRunner(client=None, oauth2=None)  # type: ignore[arg-type]
    prepared = asyncio.run(runner._prepare(TOOL_INDEX["get_posts_by_ids"], {"ids": ["1", "2"]}))
    assert prepared["query"]["ids"] == "1,2"


def test_plain_post_sends_only_text_in_json_body() -> None:
    runner = ToolRunner(client=None, oauth2=None)  # type: ignore[arg-type]
    prepared = asyncio.run(runner._prepare(TOOL_INDEX["post_tweet"], {"text": "Hello from the API"}))
    assert prepared["path"] == "/2/tweets"
    assert prepared["query"] == {}
    assert prepared["body"] == {"text": "Hello from the API"}


def test_oauth1_post_preserves_json_body_on_the_wire() -> None:
    """Authlib otherwise signs a non-form request and replaces its body with b''."""
    import httpx
    from twitter_mcp.config import OAuth1Account

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        captured["content_type"] = request.headers.get("content-type")
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(201, json={"data": {"id": "123", "text": "."}})

    async def scenario() -> None:
        account = OAuth1Account("test", "key", "secret", "token", "token-secret")
        client = TwitterClient(account)
        original_auth = client._client._auth
        await client._client.aclose()
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler), auth=original_auth,
        )
        result = await ToolRunner(client, None).run(TOOL_INDEX["post_tweet"], {"text": "."})
        assert result["data"]["id"] == "123"
        await client.aclose()

    asyncio.run(scenario())
    assert captured["body"] == b'{"text":"."}'
    assert captured["content_type"] == "application/json"
    assert str(captured["authorization"]).startswith("OAuth ")


def test_mcp_post_tweet_keeps_text_through_http_transport() -> None:
    """Exercise the public MCP route, tool runner, OAuth signer and HTTP client."""
    import httpx
    from unittest.mock import patch
    from starlette.testclient import TestClient
    from twitter_mcp.config import OAuth1Account

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(201, json={"data": {"id": "123", "text": "."}})

    account = OAuth1Account("test", "key", "secret", "token", "token-secret")
    client = TwitterClient(account)
    original_auth = client._client._auth
    asyncio.run(client._client.aclose())
    client._client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler), auth=original_auth,
    )
    with patch("twitter_mcp.server.OAuth2Client.from_env", return_value=None):
        app = create_app(client=client)
    with TestClient(app) as test_client:
        response = test_client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "post_tweet", "arguments": {"text": "."}},
        })
    asyncio.run(client.aclose())
    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"]["data"]["text"] == "."
    assert captured["body"] == b'{"text":"."}'
    assert str(captured["authorization"]).startswith("OAuth ")


def test_multipart_fields_stay_out_of_url_and_json_body() -> None:
    runner = ToolRunner(client=None, oauth2=None)  # type: ignore[arg-type]
    prepared = asyncio.run(runner._prepare(TOOL_INDEX["upload_media"], {
        "media_base64": "aGVsbG8=", "filename": "x.png", "media_type": "image/png",
        "additional_owners": ["1", "2"],
    }))
    assert prepared["query"] == {}
    assert prepared["body"] is None
    assert prepared["files"]["media"][1] == b"hello"
    assert prepared["data"]["additional_owners"] == "1,2"

    prepared = asyncio.run(runner._prepare(TOOL_INDEX["upload_compliance_submission"], {
        "job_id": "3", "file_name": "ids.txt", "file_base64": "MQo=",
    }))
    assert prepared["query"] == {}
    assert prepared["body"] is None
    assert prepared["files"]["file"][1] == b"1\n"

    prepared = asyncio.run(runner._prepare(TOOL_INDEX["upload_compliance_submission"], {
        "job_id": "3", "ids": ["1", "2"],
    }))
    assert prepared["body"] == {"ids": ["1", "2"]}
    assert prepared["files"] is None

    import pytest
    with pytest.raises(ValueError, match="exactly one"):
        asyncio.run(runner._prepare(TOOL_INDEX["upload_compliance_submission"], {
            "job_id": "3", "ids": ["1"], "file_base64": "MQo=",
        }))


def test_invalid_json_rpc_body_is_rejected() -> None:
    from starlette.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.post("/mcp", json=["not", "a request"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32600


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
    assert runner._transports(TOOL_INDEX["get_usage_credits"]) == ["app_only"]


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
    assert "Review the request fields" in str(error)
    assert "POST /2/tweets" in str(error)

    forbidden = XApiError(403, "Forbidden", "POST", "/2/tweets")
    assert "Read and write app permissions" in str(forbidden)


def test_x_error_includes_field_validation_details() -> None:
    from twitter_mcp.errors import _describe_error

    detail = _describe_error({
        "title": "Invalid Request", "detail": "One or more parameters was invalid.",
        "errors": [{"parameter": "text", "message": "Too long"}],
    })
    assert "parameter" in detail and "Too long" in detail


def test_usage_credits_uses_app_only_bearer() -> None:
    import httpx
    from twitter_mcp.config import OAuth1Account

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={"access_token": "app-bearer", "token_type": "bearer"})
        return httpx.Response(200, json={"data": {"total_balance": 12}})

    async def scenario() -> None:
        account = OAuth1Account("test", "key", "secret", "token", "token-secret")
        client = TwitterClient(account)
        await client._app_client.aclose()
        client._app_client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
        runner = ToolRunner(client, oauth2=None)
        result = await runner.run(TOOL_INDEX["get_usage_credits"], {})
        assert result["data"]["total_balance"] == 12
        await client.aclose()

    asyncio.run(scenario())
    assert [call.url.path for call in calls] == ["/oauth2/token", "/2/usage/credits"]
    assert calls[1].headers["Authorization"] == "Bearer app-bearer"

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

def test_diagnostics_endpoint_reports_the_transport_state() -> None:
    from starlette.testclient import TestClient

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/diagnostics")
        assert response.status_code == 200
        payload = response.json()
        assert "oauth1" in payload and "oauth2" in payload
        assert payload["oauth1"]["configured"] in (True, False)
        assert "probes" in payload
        assert payload["posts"]["endpoint"] == "POST /2/tweets"


def test_unsupported_authentication_errors_mention_oauth2() -> None:
    from twitter_mcp.errors import XApiError

    error = XApiError(403, "Unsupported Authentication; OAuth 1.0a User Context is forbidden", "GET", "/2/account")
    assert "OAuth 2.0" in str(error)

def test_diagnostics_latches_a_broken_oauth2_client() -> None:
    from starlette.testclient import TestClient

    class BrokenOAuth2:
        disabled_reason = None
        _tokens = type("T", (), {"scope": "tweet.read"})()

        @property
        def available(self) -> bool:
            return self.disabled_reason is None

        async def request(self, *args: object, **kwargs: object) -> dict:
            from twitter_mcp.errors import OAuth2Unavailable

            raise OAuth2Unavailable("refresh token rejected")

    app = create_app()
    app.state.runner.oauth2 = BrokenOAuth2()
    with TestClient(app) as client:
        payload = client.get("/diagnostics").json()
    assert payload["oauth2"]["usable"] is False
    assert "refresh token rejected" in payload["oauth2"]["reason"]
