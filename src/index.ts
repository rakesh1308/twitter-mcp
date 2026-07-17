import express, { Request, Response } from "express";
import { loadConfig } from "./config.js";
import { TwitterClient } from "./twitterClient.js";
import { OAuth2Client } from "./oauth2Client.js";

const config = loadConfig();
const client = new TwitterClient(config.account);
const oauth2 = OAuth2Client.fromEnv();

const app = express();
app.use(express.json());

app.get("/health", (_req: Request, res: Response) => {
  res.json({
    status: "healthy",
    account: client.getAccountName(),
    oauth2: oauth2 ? "configured" : "disabled",
    timestamp: new Date().toISOString(),
  });
});

app.get("/", (_req: Request, res: Response) => {
  res.json({
    name: "Twitter MCP Server",
    version: "1.0.0",
    description: "MCP server for Twitter API v2 (OAuth 1.0a + optional OAuth 2.0)",
    account: client.getAccountName(),
    oauth2: oauth2 ? "configured" : "disabled",
    endpoints: { health: "/health", mcp: "/mcp" },
  });
});

type ToolResult = { content: Array<{ type: "text"; text: string }>; isError?: boolean };
type ToolCallParams = { name?: string; arguments?: Record<string, unknown> };

async function handleToolCall(params: ToolCallParams): Promise<ToolResult> {
  const { name, arguments: args } = params;
  if (!name) return err("No tool name provided");

  try {
    switch (name) {
      case "post_tweet":
        return ok(await client.postTweet(args!.text as string));
      case "reply_to_tweet":
        return ok(await client.replyToTweet(args!.tweet_id as string, args!.text as string));
      case "get_tweet":
        return ok(await client.getTweet(args!.tweet_id as string));
      case "search_tweets":
        return ok(await client.searchTweets(args!.query as string, args!.max_results as number));
      case "search_all_tweets":
        return ok(await client.searchAllTweets(args!.query as string, args!.max_results as number));
      case "get_user":
        return ok(await client.getUserByUsername(args!.username as string));
      case "get_user_tweets": {
        const user = await client.getUserByUsername(args!.username as string);
        return ok(await client.getUserTweets(user.id, args!.max_results as number));
      }
      case "retweet":
        await client.retweet(args!.tweet_id as string, args!.user_id as string);
        return ok({ success: true, message: `Retweeted ${args!.tweet_id}` });
      case "like_tweet":
        await client.likeTweet(args!.tweet_id as string, args!.user_id as string);
        return ok({ success: true, message: `Liked ${args!.tweet_id}` });
      case "delete_tweet":
        await client.deleteTweet(args!.tweet_id as string);
        return ok({ success: true, message: `Deleted ${args!.tweet_id}` });
      case "list_accounts":
        return ok({ account: client.getAccountName() });
      case "follow_user":
        requireOAuth2();
        await oauth2!.followUser((await client.getMe()).id, args!.user_id as string);
        return ok({ success: true, followed: args!.user_id });
      case "unfollow_user":
        requireOAuth2();
        await oauth2!.unfollowUser((await client.getMe()).id, args!.user_id as string);
        return ok({ success: true, unfollowed: args!.user_id });
      case "get_following":
        requireOAuth2();
        return ok(await oauth2!.getFollowing((await client.getMe()).id, args!.max_results as number | undefined, args!.pagination_token as string | undefined));
      case "get_followers":
        requireOAuth2();
        return ok(await oauth2!.getFollowers((await client.getMe()).id, args!.max_results as number | undefined, args!.pagination_token as string | undefined));
      default:
        return err(`Unknown tool: ${name}`);
    }
  } catch (e) {
    return err(e instanceof Error ? e.message : String(e));
  }
}

function ok(payload: unknown): ToolResult {
  const formatted = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  return { content: [{ type: "text", text: formatted }] };
}

function err(message: string): ToolResult {
  return { content: [{ type: "text", text: JSON.stringify({ error: message }) }], isError: true };
}

function requireOAuth2(): void {
  if (!oauth2) throw new Error("OAuth 2.0 not configured. Set TWITTER_OAUTH2_* env vars.");
}

const tools = [
  tool("post_tweet", "Post a new tweet", { text: str("Tweet text (max 280 chars)") }, ["text"]),
  tool("reply_to_tweet", "Reply to a tweet", {
    tweet_id: str("ID of the tweet to reply to"),
    text: str("Reply text (max 280 chars)"),
  }, ["tweet_id", "text"]),
  tool("get_tweet", "Get tweet details", { tweet_id: str("Tweet ID") }, ["tweet_id"]),
  tool("search_tweets", "Search recent tweets (last 7 days)", {
    query: str("Search query"),
    max_results: num("1-100, default 10", 10),
  }, ["query"]),
  tool("search_all_tweets", "Search all tweets (elevated API access required)", {
    query: str("Search query"),
    max_results: num("1-100, default 10", 10),
  }, ["query"]),
  tool("get_user", "Get user info by username", { username: str("Twitter username, no @") }, ["username"]),
  tool("get_user_tweets", "Get recent tweets from a user", {
    username: str("Twitter username, no @"),
    max_results: num("1-100, default 10", 10),
  }, ["username"]),
  tool("retweet", "Retweet a tweet", {
    tweet_id: str("Tweet ID to retweet"),
    user_id: str("Your numeric Twitter user ID (get from get_user)"),
  }, ["tweet_id", "user_id"]),
  tool("like_tweet", "Like a tweet", {
    tweet_id: str("Tweet ID to like"),
    user_id: str("Your numeric Twitter user ID (get from get_user)"),
  }, ["tweet_id", "user_id"]),
  tool("delete_tweet", "Delete one of your tweets", { tweet_id: str("Tweet ID to delete") }, ["tweet_id"]),
  tool("list_accounts", "Show configured account", {}, []),
  tool("follow_user", "Follow a user (OAuth 2.0)", {
    user_id: str("Numeric Twitter user ID to follow"),
  }, ["user_id"]),
  tool("unfollow_user", "Unfollow a user (OAuth 2.0)", {
    user_id: str("Numeric Twitter user ID to unfollow"),
  }, ["user_id"]),
  tool("get_following", "List accounts you follow (OAuth 2.0)", {
    max_results: num("1-1000, default 100", 100),
    pagination_token: str("Pagination token from previous response"),
  }, []),
  tool("get_followers", "List accounts following you (OAuth 2.0)", {
    max_results: num("1-1000, default 100", 100),
    pagination_token: str("Pagination token from previous response"),
  }, []),
];

function str(description: string) {
  return { type: "string" as const, description };
}
function num(description: string, dflt: number) {
  return { type: "number" as const, description, default: dflt };
}
function tool(name: string, description: string, properties: Record<string, unknown>, required: string[]) {
  return {
    name,
    description,
    inputSchema: { type: "object" as const, properties, ...(required.length ? { required } : {}) },
  };
}

app.all("/mcp", async (req: Request, res: Response) => {
  try {
    const body = req.body;
    if (!body || !body.method) {
      res.json({ jsonrpc: "2.0", id: body?.id ?? null, error: { code: -32600, message: "Invalid request" } });
      return;
    }
    let result: unknown;
    switch (body.method) {
      case "initialize":
        result = {
          protocolVersion: "2025-03-26",
          capabilities: { tools: {} },
          serverInfo: { name: "twitter-mcp-server", version: "1.0.0" },
        };
        break;
      case "tools/list":
        result = { tools };
        break;
      case "tools/call":
        result = await handleToolCall(body.params);
        break;
      case "ping":
        result = {};
        break;
      default:
        res.json({ jsonrpc: "2.0", id: body.id, error: { code: -32601, message: "Method not found" } });
        return;
    }
    res.json({ jsonrpc: "2.0", id: body.id, result });
  } catch (e) {
    console.error("[mcp]", e);
    res.status(500).json({ jsonrpc: "2.0", id: null, error: { code: -32603, message: e instanceof Error ? e.message : String(e) } });
  }
});

const PORT = config.port;
const HOST = config.host;

app.listen(PORT, HOST, () => {
  console.log(`[mcp] Twitter MCP Server listening on http://${HOST}:${PORT}/mcp (account=${client.getAccountName()}, oauth2=${oauth2 ? "on" : "off"})`);
});

process.on("SIGTERM", () => {
  console.log("[mcp] shutting down");
  process.exit(0);
});