# Twitter MCP Server

A Model Context Protocol (MCP) server for Twitter API v2 with OAuth 1.0a authentication. Deploy to Zeabur and use with any AI client that supports MCP.

## Features

- **Multi-account support**: Configure up to 2 Twitter accounts
- **OAuth 1.0a authentication**: More reliable than Bearer Token
- **Post tweets**: Create new tweets
- **Reply to tweets**: Reply to existing tweets
- **Search tweets**: Search recent or all tweets
- **Get tweet data**: Retrieve tweet details by ID
- **User lookup**: Get user information by username
- **User tweets**: Get recent tweets from a user
- **Retweet/Like**: Interact with tweets
- **Delete tweets**: Remove your tweets
- **Streamable HTTP transport**: Works with remote MCP clients

## Prerequisites

1. Node.js 20+ installed locally
2. Twitter Developer account with API access (Basic, Pro, or Free tier)
3. Zeabur account for deployment

## Twitter API Setup

1. Go to [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Create a Project and App (required for API v2 access)
3. Navigate to "Keys and tokens" tab for your App
4. Generate the following credentials:
   - **API Key** - Consumer API Key
   - **API Secret** - Consumer API Secret
   - **Access Token** - User Access Token (under "Authentication Tokens")
   - **Access Token Secret** - User Access Token Secret

### Required API Permissions

Make sure your app has **Read and Write** permissions in your Twitter Developer Portal:
- **Read** - For reading tweets, searching, user info
- **Write** - For posting, replying, deleting tweets

## Local Development

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Account 1 Configuration (Required)
ACCOUNT1_NAME=MyMainAccount
ACCOUNT1_API_KEY=your_api_key_here
ACCOUNT1_API_SECRET=your_api_secret_here
ACCOUNT1_ACCESS_TOKEN=your_access_token_here
ACCOUNT1_ACCESS_TOKEN_SECRET=your_access_token_secret_here

# Account 2 Configuration (optional)
ACCOUNT2_NAME=MySecondAccount
ACCOUNT2_API_KEY=your_second_api_key_here
ACCOUNT2_API_SECRET=your_second_api_secret_here
ACCOUNT2_ACCESS_TOKEN=your_second_access_token_here
ACCOUNT2_ACCESS_TOKEN_SECRET=your_second_access_token_secret_here

# Server Configuration
PORT=3000
HOST=0.0.0.0
```

### 3. Run Development Server

```bash
npm run dev
```

The server will start on `http://localhost:3000`

### 4. Test the Server

```bash
# Health check
curl http://localhost:3000/health

# Get server info
curl http://localhost:3000/
```

## Deployment to Zeabur

### Option 1: Deploy from GitHub

1. Push your code to a GitHub repository
2. Go to [Zeabur](https://zeabur.com) and sign in
3. Click "Deploy New Service"
4. Select "GitHub" and connect your repository
5. Configure environment variables:
   - `ACCOUNT1_API_KEY`
   - `ACCOUNT1_API_SECRET`
   - `ACCOUNT1_ACCESS_TOKEN`
   - `ACCOUNT1_ACCESS_TOKEN_SECRET`
   - (And similar for Account 2)
6. Deploy - Zeabur will automatically detect the Node.js app and deploy it

### Option 2: Deploy with Dockerfile

1. The `Dockerfile` is already included in this project
2. Upload your code to Zeabur
3. Zeabur will use the Dockerfile to build and deploy

### Environment Variables on Zeabur

Configure these in Zeabur's environment variables panel:

| Variable | Description | Required |
|----------|-------------|----------|
| `ACCOUNT1_API_KEY` | API Key for account 1 | Yes |
| `ACCOUNT1_API_SECRET` | API Secret for account 1 | Yes |
| `ACCOUNT1_ACCESS_TOKEN` | Access Token for account 1 | Yes |
| `ACCOUNT1_ACCESS_TOKEN_SECRET` | Access Token Secret for account 1 | Yes |
| `ACCOUNT2_API_KEY` | API Key for account 2 | If using 2nd account |
| `ACCOUNT2_API_SECRET` | API Secret for account 2 | If using 2nd account |
| `ACCOUNT2_ACCESS_TOKEN` | Access Token for account 2 | If using 2nd account |
| `ACCOUNT2_ACCESS_TOKEN_SECRET` | Access Token Secret for account 2 | If using 2nd account |
| `PORT` | Server port (default: 3000) | No |

## AI Client Configuration

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "twitter": {
      "type": "streamable-http",
      "url": "https://your-zeabur-app.zeabur.app/mcp"
    }
  }
}
```

### Cursor

Add to Cursor's MCP settings:

```json
{
  "mcpServers": {
    "twitter": {
      "type": "streamable-http",
      "url": "https://your-zeabur-app.zeabur.app/mcp"
    }
  }
}
```

### Other MCP Clients

Use the URL format: `https://your-zeabur-app.zeabur.app/mcp` with transport type `streamable-http`.

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `post_tweet` | Post a new tweet | `text`, `account` (optional) |
| `reply_to_tweet` | Reply to a tweet | `tweet_id`, `text`, `account` (optional) |
| `get_tweet` | Get tweet details | `tweet_id` |
| `search_tweets` | Search recent tweets | `query`, `max_results` (optional) |
| `search_all_tweets` | Search all tweets | `query`, `max_results` (optional) |
| `get_user` | Get user info | `username` |
| `get_user_tweets` | Get user's tweets | `username`, `max_results` (optional) |
| `retweet` | Retweet a tweet | `tweet_id`, `user_id`, `account` (optional) |
| `like_tweet` | Like a tweet | `tweet_id`, `user_id`, `account` (optional) |
| `delete_tweet` | Delete a tweet | `tweet_id`, `account` (optional) |
| `list_accounts` | List configured accounts | none |

## Example Usage

### Post a tweet
```
Use post_tweet with {"text": "Hello from MCP!", "account": "MyMainAccount"}
```

### Reply to a tweet
```
Use reply_to_tweet with {"tweet_id": "123456789", "text": "Great post!", "account": "MyMainAccount"}
```

### Search for tweets
```
Use search_tweets with {"query": "AI", "max_results": 10}
```

### Get user info
```
Use get_user with {"username": "twitterdev"}
```

## Project Structure

```
twitter-mcp/
├── src/
│   ├── index.ts       # Main MCP server with Express
│   ├── config.ts      # Configuration loader
│   ├── twitterClient.ts  # Twitter API client with OAuth 1.0a
│   └── types.ts       # TypeScript types
├── Dockerfile         # Docker deployment
├── package.json       # Dependencies
├── tsconfig.json      # TypeScript config
├── .env.example      # Example environment file
└── README.md          # This file
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server info |
| `/health` | GET | Health check |
| `/mcp` | GET/POST | MCP protocol endpoint |

## Troubleshooting

### "No Twitter accounts configured" error
- Ensure your `.env` file exists and has all 4 required variables for ACCOUNT1
- Check for typos in variable names
- All four are required: API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET

### "OAuth 1.0a requires access token and secret" error
- Make sure you have provided ACCESS_TOKEN and ACCESS_TOKEN_SECRET
- These are different from API Key/Secret

### 403 Forbidden error
- Ensure your App is attached to a Project
- Verify your App has Read+Write permissions
- Check that your Access Token has the right permissions

### Rate limiting
- Twitter API has rate limits (varies by endpoint and tier)
- Free tier: ~450 requests per 15 minutes
- Implement exponential backoff for retry logic if needed

## License

MIT