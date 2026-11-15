# Twitter MCP Server (Python)

Model Context Protocol (MCP) server for the Twitter/X API v2. Single account, OAuth 1.0a for read/write, with optional OAuth 2.0 for follow/explore tools. Deploys cleanly to Zeabur.

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Server info (JSON) |
| `/health` | GET | Health probe |
| `/mcp` | POST | MCP JSON-RPC |

## Tools

OAuth 1.0a (always required):

| Tool | Description | Parameters |
|------|-------------|------------|
| `post_tweet` | Post a new tweet | `text` |
| `reply_to_tweet` | Reply to a tweet | `tweet_id`, `text` |
| `get_tweet` | Get tweet details | `tweet_id` |
| `search_tweets` | Search recent tweets | `query`, `max_results?` |
| `search_all_tweets` | Search all tweets (elevated access) | `query`, `max_results?` |
| `get_user` | Get user info | `username` |
| `get_user_tweets` | Get a user's recent tweets | `username`, `max_results?` |
| `retweet` | Retweet a tweet | `tweet_id`, `user_id` |
| `like_tweet` | Like a tweet | `tweet_id`, `user_id` |
| `delete_tweet` | Delete one of your tweets | `tweet_id` |
| `list_accounts` | Show configured account | — |

OAuth 2.0 (optional — requires `TWITTER_OAUTH2_*` env vars):

| Tool | Description | Parameters |
|------|-------------|------------|
| `follow_user` | Follow a user | `user_id` |
| `unfollow_user` | Unfollow a user | `user_id` |
| `get_following` | List accounts you follow | `max_results?`, `pagination_token?` |
| `get_followers` | List accounts following you | `max_results?`, `pagination_token?` |

## Environment variables (Zeabur → Variables)

**Required — OAuth 1.0a**

| Variable | Notes |
|----------|-------|
| `TWITTER_API_KEY` | App Consumer Key |
| `TWITTER_API_SECRET` | App Consumer Secret |
| `TWITTER_ACCESS_TOKEN` | User Access Token (Read+Write permission) |
| `TWITTER_ACCESS_TOKEN_SECRET` | User Access Token Secret |
| `ACCOUNT_NAME` | Optional display name, default `Twitter Account` |
| `HOST` | Optional, default `0.0.0.0` |
| `PORT` | Leave unset — Zeabur injects this |

**Optional — OAuth 2.0 (follow/explore)**

| Variable | Notes |
|----------|-------|
| `TWITTER_OAUTH2_CLIENT_ID` | App's OAuth 2.0 Client ID |
| `TWITTER_OAUTH2_CLIENT_SECRET` | App's OAuth 2.0 Client Secret |
| `TWITTER_OAUTH2_ACCESS_TOKEN` | Bootstrap access token |
| `TWITTER_OAUTH2_REFRESH_TOKEN` | Bootstrap refresh token |
| `TWITTER_OAUTH2_SCOPE` | e.g. `tweet.read users.read follows.read follows.write offline.access` |
| `TWITTER_OAUTH2_TOKEN_FILE` | Default `/data/oauth2.json` — **must be on a persistent volume** |
| `OAUTH2_REFRESH_SKEW_SECONDS` | Default `60` |

Tokens auto-refresh on expiry and persist to `TWITTER_OAUTH2_TOKEN_FILE`. On Zeabur, mount a persistent volume at `/data` so the file survives redeploys.

## Deploy to Zeabur

1. Push to GitHub.
2. Zeabur → **Deploy New Service → GitHub** → select repo.
3. Zeabur auto-detects Python (uses the Dockerfile).
4. Add the four `TWITTER_*` variables above (and the OAuth 2.0 set if you want follow/explore).
5. Add a **Persistent Volume** mounted at `/data`.
6. Deploy. Public URL is `https://<project>.zeabur.app`.

## Deploy to Vercel

Import the repository from Git and use the FastAPI framework preset with the
repository root. Vercel loads the ASGI app from `app.py`. No build command,
output directory, or `HOST` and `PORT` settings are needed.

In the Vercel project, enable Vercel Authentication for **All Deployments**
under Deployment Protection before adding credentials. This includes the
production domain. The app relies on Vercel to authenticate requests.

Add the four OAuth 1.0a variables listed above as Production secrets. Redeploy
if the variables were added after the initial deployment.

Connect an MCP client over Streamable HTTP at
`https://<project>.vercel.app/mcp`. For an unattended client that can send
custom headers, use Vercel's Protection Bypass for Automation and pass its
secret as the `x-vercel-protection-bypass` header. Check `GET /health` with
Vercel access for runtime configuration status.

Leave the optional OAuth 2.0 variables unset on Vercel. Their current token
refresh implementation needs durable storage for the rotated refresh token.

## Connect from an MCP client

Streamable HTTP at `/mcp`:

```json
{
  "mcpServers": {
    "twitter": {
      "type": "streamable-http",
      "url": "https://<project>.zeabur.app/mcp"
    }
  }
}
```

## Local development

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # or: source .venv/bin/activate
pip install -e .

TWITTER_API_KEY=... \
TWITTER_API_SECRET=... \
TWITTER_ACCESS_TOKEN=... \
TWITTER_ACCESS_TOKEN_SECRET=... \
python -m twitter_mcp
```

## Project layout

```
twitter-mcp/
├── src/twitter_mcp/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py        # env → typed config
│   ├── oauth1.py        # OAuth 1.0a Twitter client (httpx + authlib)
│   ├── oauth2.py        # OAuth 2.0 + token persistence + auto-refresh
│   └── server.py        # Starlette + JSON-RPC at /mcp
├── Dockerfile
├── .dockerignore
├── pyproject.toml
├── .env.example
└── README.md
```

## License

MIT