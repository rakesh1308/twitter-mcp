# Twitter MCP Server (Python)

Model Context Protocol server for the **full X API v2 surface** - 251 curated tools covering 245 of the 260
operations in the official X API v2 OpenAPI specification, plus a generic escape hatch that reaches every
remaining operation (including the live streaming endpoints).

OAuth 1.0a is always required; OAuth 2.0 is optional and unlocks media, DMs, Chat, Spaces and the scoped
endpoints.

## Coverage

Baseline: official X API v2 OpenAPI spec **v2.174** (`https://api.x.com/2/openapi.json`), 202 paths /
260 operations / 24 endpoint families.

| Metric | Value |
|--------|-------|
| Curated MCP tools | 251 |
| X API operations with a dedicated tool | 245 / 260 (94.2%) |
| Endpoint families fully covered | 23 / 24 |
| Remaining operations | 15 live streaming endpoints (firehose / sample / filtered stream) - reachable through `x_api_request` |
| Operations reachable in total | 260 / 260 (100%) |

| Family | Dedicated tools | Operations |
|--------|-----------------|------------|
| Posts | 14 | 14 / 14 |
| Users (incl. follows, blocks, mutes, bookmarks) | 27 | 46 / 46 |
| Likes and reposts | 6 | 6 / 6 |
| Lists | 16 | 9 / 9 |
| Media | 9 | 11 / 11 |
| Trends | 2 | 2 / 2 |
| Spaces | 6 | 6 / 6 |
| Direct Messages | 8 | 9 / 9 |
| Chat | 40 | 45 / 45 |
| Communities | 2 | 2 / 2 |
| Community Notes | 5 | 5 / 5 |
| News | 2 | 2 / 2 |
| Compliance | 6 | 6 / 6 |
| Broadcasts | 30 | 40 / 40 |
| Calls | 10 | 10 / 10 |
| Bots | 6 | 6 / 6 |
| Webhooks | 8 | 8 / 8 |
| Activity | 5 | 5 / 5 |
| Account Activity | 5 | 5 / 5 |
| Stream (rules management) | 3 | 3 / 3 |
| Articles | 2 | 2 / 2 |
| Account / Usage / Connections / General | 9 | 9 / 9 |
| Escape hatch (`x_api_request`) | 1 | covers every remaining operation |

Live proof is served by the running server:

| Endpoint | Purpose |
|----------|---------|
| `POST /mcp` | MCP JSON-RPC (`initialize`, `tools/list`, `tools/call`, `ping`) |
| `GET /health` | Health probe, credential and tool count status |
| `GET /tools-manifest.json` | Full machine readable tool catalog with JSON schemas |
| `GET /api-coverage` | Coverage report against the official specification |

## What changed in 2.0.0

Every issue found in the 1.x coverage audit is resolved:

| Issue | Fix |
|-------|-----|
| Search query was interpolated into the URL, truncating at `&` and `#` | All query values are sent as structured parameters, so httpx percent-encodes them (regression test included) |
| No tool exposed the authenticated account id | New `get_me` tool; `list_accounts` kept as an alias of `GET /2/users/me` |
| No media upload, so images/video/GIFs could not be posted | `upload_media` (multipart), chunked upload tools, subtitles and metadata tools; `post_tweet` accepts `media_ids` |
| Pagination was impossible on read tools | `pagination_token` exposed on search, user posts, lists, followers, DMs and more |
| Field sets were hard-coded | `tweet_fields`, `user_fields`, `media_fields`, `expansions` are now caller-controlled parameters |
| Integer parameters were typed as `number` | Schemas now use JSON Schema `integer` with `minimum` / `maximum` |
| `list_accounts` mapped to no API operation | It now calls `GET /2/users/me` |
| Client used the legacy `api.twitter.com` host | Now uses the documented `https://api.x.com` host |
| Blocking HTTP calls in the event loop | Both clients are now async (`httpx.AsyncClient`) |
| Only 15 of 260 operations were reachable | 251 curated tools, every family covered, plus a generic escape hatch |

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/mcp` | POST | MCP JSON-RPC (Streamable HTTP) |
| `/health` | GET | Health probe |
| `/tools-manifest.json` | GET | Tool catalog with schemas |
| `/api-coverage` | GET | API coverage report |
| `/` | GET | Server info |

## Authentication

### OAuth 1.0a (always required)

`TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`.

### OAuth 2.0 (optional)

`TWITTER_OAUTH2_CLIENT_ID`, `TWITTER_OAUTH2_CLIENT_SECRET`, `TWITTER_OAUTH2_ACCESS_TOKEN`,
`TWITTER_OAUTH2_REFRESH_TOKEN`, `TWITTER_OAUTH2_SCOPE`, `TWITTER_OAUTH2_TOKEN_FILE`.

Recommended scope:

```
tweet.read tweet.write users.read follows.read follows.write like.read like.write
list.read list.write bookmark.read bookmark.write media.write mute.read mute.write
block.read block.write dm.read dm.write space.read offline.access
```

Tokens auto-refresh on expiry and persist to `TWITTER_OAUTH2_TOKEN_FILE` (mount a persistent volume at
`/data` on Zeabur). When both transports are configured the server picks the working one automatically and
falls back to the other on a 401/403.

## Deploy to Vercel

The `twitter-mcp` Vercel project is already connected to `rakesh1308/twitter-mcp` with `main` as the production
branch, so **every push to `main` is built and deployed automatically** - no CLI step is needed. The repository
contains the Vercel Python function (`api/index.py` + `vercel.json` + `requirements.txt`) that the build uses.

To deploy by hand (for example after changing environment variables), use the CLI:

```bash
npm i -g vercel
vercel            # first run: link the project
vercel env add TWITTER_API_KEY production
vercel env add TWITTER_API_SECRET production
vercel env add TWITTER_ACCESS_TOKEN production
vercel env add TWITTER_ACCESS_TOKEN_SECRET production
# optional OAuth 2.0
vercel env add TWITTER_OAUTH2_CLIENT_ID production
vercel env add TWITTER_OAUTH2_CLIENT_SECRET production
vercel env add TWITTER_OAUTH2_ACCESS_TOKEN production
vercel env add TWITTER_OAUTH2_REFRESH_TOKEN production
vercel env add TWITTER_OAUTH2_SCOPE production
vercel --prod
```

The MCP endpoint is then available at `https://<deployment>.vercel.app/mcp`.

> Serverless note: requests are stateless, so set `TWITTER_OAUTH2_TOKEN_FILE` to a writable path (for example
> `/tmp/oauth2.json`) on Vercel - the token is refreshed from the refresh token on every cold start.

### Live deployment

| What | URL |
|------|-----|
| MCP endpoint | `https://twitter-mcp-rakesh1308s-projects.vercel.app/mcp` |
| Health | `https://twitter-mcp-rakesh1308s-projects.vercel.app/health` |
| Coverage report | `https://twitter-mcp-rakesh1308s-projects.vercel.app/api-coverage` |
| Tool manifest | `https://twitter-mcp-rakesh1308s-projects.vercel.app/tools-manifest.json` |
| Vercel project | `twitter-mcp` (aliases: `twitter-mcp-delta.vercel.app`) |

The deployment already carries the OAuth 1.0a credentials (`TWITTER_API_KEY`, `TWITTER_API_SECRET`,
`TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`), so posts, searches, users, lists, bookmarks, likes,
reposts, follows and the generic `x_api_request` escape hatch work out of the box.

The OAuth 2.0 variables are not set yet. Endpoints that X only serves to OAuth 2.0 clients (trends, media
upload, direct messages, Chat and Spaces) answer with a clear error until the `TWITTER_OAUTH2_*` variables are
added in the Vercel dashboard; add them and redeploy to unlock those families:

```
vercel env add TWITTER_OAUTH2_CLIENT_ID production
vercel env add TWITTER_OAUTH2_CLIENT_SECRET production
vercel env add TWITTER_OAUTH2_ACCESS_TOKEN production
vercel env add TWITTER_OAUTH2_REFRESH_TOKEN production
vercel env add TWITTER_OAUTH2_SCOPE production
```

> Vercel Authentication (SSO protection) is disabled for production so that MCP clients can reach the
> endpoint; preview deployments stay protected.

## Deploy with Docker / Zeabur

```bash
docker build -t twitter-mcp .
docker run -p 3000:3000 --env-file .env twitter-mcp
```

Zeabur auto-detects the Python Dockerfile. Add the `TWITTER_*` variables and mount a persistent volume at
`/data`.

## Connect from an MCP client

Streamable HTTP:

```json
{
  "mcpServers": {
    "twitter": {
      "type": "streamable-http",
      "url": "https://<deployment>.vercel.app/mcp"
    }
  }
}
```

## The escape hatch

`x_api_request` calls any documented operation directly, for example:

```json
{
  "name": "x_api_request",
  "arguments": {
    "method": "GET",
    "path": "/2/users/2244994945/affiliates",
    "query": { "max_results": "10" },
    "auth": "auto"
  }
}
```

Paths must be relative and start with `/2/`, `/1.1/` or `/oauth2/`; absolute URLs are rejected.

## Local development

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest tests -q
python -m twitter_mcp
```

## Project layout

```
twitter-mcp/
├── api/index.py            # Vercel serverless entrypoint
├── src/twitter_mcp/
│   ├── api.py              # tool catalog (posts, users, likes, lists, media, trends, ...)
│   ├── api_extended.py     # tool catalog (chat, broadcasts, calls, bots, compliance, ...)
│   ├── server.py           # ASGI app, MCP JSON-RPC, tool dispatch, coverage report
│   ├── oauth1.py           # async OAuth 1.0a client
│   ├── oauth2.py           # async OAuth 2.0 client with token refresh
│   ├── config.py           # environment -> typed config
│   ├── errors.py           # shared X API error type
│   └── x_api_operations.json  # snapshot of the official OpenAPI operations
├── tests/                  # contract + coverage tests
├── vercel.json
├── requirements.txt
└── Dockerfile
```

## License

MIT