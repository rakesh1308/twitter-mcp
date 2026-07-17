# Twitter MCP Server

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
| `search_all_tweets` | Search all tweets (elevated API access) | `query`, `max_results?` |
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
| `TWITTER_OAUTH2_EXPIRES_AT` | ISO timestamp or epoch seconds |
| `TWITTER_OAUTH2_SCOPE` | e.g. `tweet.read users.read follows.read follows.write offline.access` |
| `TWITTER_OAUTH2_TOKEN_FILE` | Default `/data/oauth2.json` — **must be on a persistent volume** |
| `OAUTH2_REFRESH_SKEW_SECONDS` | Default `60` |

Tokens auto-refresh on expiry and persist to `TWITTER_OAUTH2_TOKEN_FILE`. On Zeabur, mount a persistent volume at `/data` so the file survives redeploys.

## Deploy to Zeabur

1. Push to GitHub.
2. Zeabur → **Deploy New Service → GitHub** → select repo.
3. Add the four `TWITTER_*` variables above (and the OAuth 2.0 set if you want follow/explore).
4. Add a **Persistent Volume** mounted at `/data`.
5. Deploy. Public URL is `https://<project>.zeabur.app`.

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
TWITTER_API_KEY=... \
TWITTER_API_SECRET=... \
TWITTER_ACCESS_TOKEN=... \
TWITTER_ACCESS_TOKEN_SECRET=... \
npm run dev
```

## Project layout

```
twitter-mcp/
├── src/
│   ├── config.ts         # env → typed config
│   ├── index.ts          # Express server + MCP JSON-RPC
│   ├── oauth2Client.ts   # OAuth 2.0 + token persistence + auto-refresh
│   ├── twitterClient.ts  # OAuth 1.0a Twitter API v2 client
│   └── types.ts          # Shared types
├── Dockerfile
├── .dockerignore
├── package.json
├── tsconfig.json
└── README.md
```

## License

MIT