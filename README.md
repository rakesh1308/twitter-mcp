# Twitter MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/Node.js-20%2B-green.svg)](https://nodejs.org/)
[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-blue.svg)](https://modelcontextprotocol.io/)
[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com)

A **Model Context Protocol (MCP) server** that gives AI assistants (Claude, Cursor, etc.) full Twitter/X API access via OAuth 1.0a. Deploy once to the cloud, connect from any MCP-compatible client.

## What it does

Let your AI assistant post tweets, reply, search, get user info, retweet, like, and delete — all from natural language. No manual API calls needed.

```
"Post a tweet saying hello from my AI assistant"
"Search for recent tweets about Claude AI and summarize them"
"Reply to tweet 123456 with a thank you message"
```

## Features

- **OAuth 1.0a authentication** — more reliable than Bearer Token for write operations
- **Full tweet lifecycle** — post, reply, retweet, like, delete
- **Search** — recent tweets or all tweets (with elevated access)
- **User lookup** — get profile info and recent tweets by username
- **Multi-account support** — configure up to 2 Twitter accounts and switch between them
- **Streamable HTTP transport** — works with any remote MCP client
- **Docker ready** — includes Dockerfile for easy deployment

## Quick Start

### 1. Get Twitter API Credentials

1. Go to the [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Create a Project and App
3. Set App permissions to **Read and Write**
4. Under "Keys and tokens", generate:
   - API Key & API Secret
   - Access Token & Access Token Secret

### 2. Deploy to Zeabur (recommended)

1. Fork this repo
2. Go to [Zeabur](https://zeabur.com) → Deploy New Service → GitHub
3. Select your fork
4. Add these environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `ACCOUNT1_NAME` | Display name for account 1 | Yes |
| `ACCOUNT1_API_KEY` | API Key | Yes |
| `ACCOUNT1_API_SECRET` | API Secret | Yes |
| `ACCOUNT1_ACCESS_TOKEN` | Access Token | Yes |
| `ACCOUNT1_ACCESS_TOKEN_SECRET` | Access Token Secret | Yes |
| `ACCOUNT2_NAME` | Display name for account 2 | No |
| `ACCOUNT2_API_KEY` | API Key for account 2 | No |
| `ACCOUNT2_API_SECRET` | API Secret for account 2 | No |
| `ACCOUNT2_ACCESS_TOKEN` | Access Token for account 2 | No |
| `ACCOUNT2_ACCESS_TOKEN_SECRET` | Access Token Secret for account 2 | No |
| `PORT` | Server port (default: 3000) | No |

5. Deploy — Zeabur detects Node.js automatically and builds from the Dockerfile

### 3. Connect your AI Client

**Claude Desktop** — add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "twitter": {
      "type": "streamable-http",
      "url": "https://your-app.zeabur.app/mcp"
    }
  }
}
```

**Cursor** — add to MCP settings:
```json
{
  "mcpServers": {
    "twitter": {
      "type": "streamable-http",
      "url": "https://your-app.zeabur.app/mcp"
    }
  }
}
```

Any MCP client that supports `streamable-http` transport works with the same URL pattern.

## Local Development

```bash
# Install dependencies
npm install

# Copy example env and fill in your credentials
cp .env.example .env

# Start dev server (with hot reload)
npm run dev

# Verify it's running
curl http://localhost:3000/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `post_tweet` | Post a new tweet | `text`, `account` (optional) |
| `reply_to_tweet` | Reply to a tweet | `tweet_id`, `text`, `account` (optional) |
| `get_tweet` | Get tweet details | `tweet_id` |
| `search_tweets` | Search recent tweets | `query`, `max_results` (optional) |
| `search_all_tweets` | Search all tweets (elevated access) | `query`, `max_results` (optional) |
| `get_user` | Get user profile | `username` |
| `get_user_tweets` | Get a user's recent tweets | `username`, `max_results` (optional) |
| `retweet` | Retweet a tweet | `tweet_id`, `user_id`, `account` (optional) |
| `like_tweet` | Like a tweet | `tweet_id`, `user_id`, `account` (optional) |
| `delete_tweet` | Delete a tweet | `tweet_id`, `account` (optional) |
| `list_accounts` | List configured accounts | — |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server info |
| `/health` | GET | Health check |
| `/mcp` | GET/POST | MCP protocol endpoint |

## Project Structure

```
twitter-mcp/
├── src/
│   ├── index.ts          # MCP server + Express app
│   ├── config.ts         # Environment variable loader
│   ├── twitterClient.ts  # Twitter API client (OAuth 1.0a)
│   └── types.ts          # TypeScript types
├── Dockerfile
├── package.json
├── tsconfig.json
├── .env.example
└── README.md
```

## Troubleshooting

**"No Twitter accounts configured"**
- Ensure `.env` exists with all 4 required `ACCOUNT1_*` variables

**"OAuth 1.0a requires access token and secret"**
- `ACCESS_TOKEN` and `ACCESS_TOKEN_SECRET` are different from `API_KEY`/`API_SECRET` — generate them separately in the developer portal

**403 Forbidden**
- Make sure your App is attached to a Project in the developer portal
- Verify App permissions are set to **Read and Write**
- Regenerate Access Tokens *after* changing permissions (old tokens don't pick up new permissions)

**Rate limiting**
- Free tier: ~450 requests per 15 minutes per endpoint
- Basic/Pro tiers have higher limits — check the [Twitter API docs](https://developer.twitter.com/en/docs/twitter-api/rate-limits)

## License

MIT
