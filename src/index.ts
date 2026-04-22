import "dotenv/config";
import express, { Request, Response } from "express";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequest,
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { loadConfig } from "./config.js";
import { TwitterClient } from "./twitterClient.js";

// Load configuration
const config = loadConfig();

// Create Twitter clients for each account
const clients: TwitterClient[] = config.accounts.map(
  (account) => new TwitterClient(account)
);

// Create Express app
const app = express();
app.use(express.json());

// Health check endpoint
app.get("/health", (req: Request, res: Response) => {
  res.json({
    status: "healthy",
    accounts: clients.map((c) => c.getAccountName()),
    timestamp: new Date().toISOString(),
  });
});

// Root endpoint for info
app.get("/", (req: Request, res: Response) => {
  res.json({
    name: "Twitter MCP Server",
    version: "1.0.0",
    description: "MCP server for Twitter API v2 with Streamable HTTP transport",
    accounts: clients.map((c) => c.getAccountName()),
    endpoints: {
      health: "/health",
      mcp: "/mcp",
    },
  });
});

// Parse account from request
function getAccountClient(accountName?: string): TwitterClient {
  if (!accountName) {
    return clients[0];
  }
  const client = clients.find((c) => c.getAccountName() === accountName);
  if (!client) {
    throw new Error(
      `Account '${accountName}' not found. Available accounts: ${clients
        .map((c) => c.getAccountName())
        .join(", ")}`
    );
  }
  return client;
}

// Create MCP server
const server = new Server(
  {
    name: "twitter-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Define all the MCP tools
const tools = [
  // Post a new tweet
  {
    name: "post_tweet",
    description: "Post a new tweet to Twitter",
    inputSchema: {
      type: "object",
      properties: {
        text: {
          type: "string",
          description: "The text content of the tweet (max 280 characters)",
        },
        account: {
          type: "string",
          description:
            "Account name to use (optional, defaults to first account)",
        },
      },
      required: ["text"],
    },
  },
  // Reply to a tweet
  {
    name: "reply_to_tweet",
    description: "Reply to an existing tweet",
    inputSchema: {
      type: "object",
      properties: {
        tweet_id: {
          type: "string",
          description: "The ID of the tweet to reply to",
        },
        text: {
          type: "string",
          description: "The text content of your reply (max 280 characters)",
        },
        account: {
          type: "string",
          description:
            "Account name to use (optional, defaults to first account)",
        },
      },
      required: ["tweet_id", "text"],
    },
  },
  // Get tweet by ID
  {
    name: "get_tweet",
    description: "Get details of a specific tweet by its ID",
    inputSchema: {
      type: "object",
      properties: {
        tweet_id: {
          type: "string",
          description: "The ID of the tweet to retrieve",
        },
      },
      required: ["tweet_id"],
    },
  },
  // Search tweets
  {
    name: "search_tweets",
    description: "Search for recent tweets matching a query",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description:
            "Search query (supports Twitter search operators like 'from:', 'has:images', etc.)",
        },
        max_results: {
          type: "number",
          description: "Maximum number of results (1-100, default: 10)",
          default: 10,
        },
      },
      required: ["query"],
    },
  },
  // Search all tweets (requires elevated access)
  {
    name: "search_all_tweets",
    description: "Search across all tweets (requires elevated API access)",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Search query",
        },
        max_results: {
          type: "number",
          description: "Maximum number of results (1-100, default: 10)",
          default: 10,
        },
      },
      required: ["query"],
    },
  },
  // Get user by username
  {
    name: "get_user",
    description: "Get Twitter user information by username",
    inputSchema: {
      type: "object",
      properties: {
        username: {
          type: "string",
          description: "The Twitter username (without @)",
        },
      },
      required: ["username"],
    },
  },
  // Get user tweets
  {
    name: "get_user_tweets",
    description: "Get recent tweets from a specific user",
    inputSchema: {
      type: "object",
      properties: {
        username: {
          type: "string",
          description: "The Twitter username (without @)",
        },
        max_results: {
          type: "number",
          description: "Maximum number of results (1-100, default: 10)",
          default: 10,
        },
      },
      required: ["username"],
    },
  },
  // Retweet
  {
    name: "retweet",
    description: "Retweet an existing tweet",
    inputSchema: {
      type: "object",
      properties: {
        tweet_id: {
          type: "string",
          description: "The ID of the tweet to retweet",
        },
        user_id: {
          type: "string",
          description:
            "Your Twitter user ID (required for retweeting, get from get_user)",
        },
        account: {
          type: "string",
          description:
            "Account name to use (optional, defaults to first account)",
        },
      },
      required: ["tweet_id", "user_id"],
    },
  },
  // Like tweet
  {
    name: "like_tweet",
    description: "Like a tweet",
    inputSchema: {
      type: "object",
      properties: {
        tweet_id: {
          type: "string",
          description: "The ID of the tweet to like",
        },
        user_id: {
          type: "string",
          description:
            "Your Twitter user ID (required for liking, get from get_user)",
        },
        account: {
          type: "string",
          description:
            "Account name to use (optional, defaults to first account)",
        },
      },
      required: ["tweet_id", "user_id"],
    },
  },
  // Delete tweet
  {
    name: "delete_tweet",
    description: "Delete one of your tweets",
    inputSchema: {
      type: "object",
      properties: {
        tweet_id: {
          type: "string",
          description: "The ID of the tweet to delete",
        },
        account: {
          type: "string",
          description:
            "Account name to use (optional, defaults to first account)",
        },
      },
      required: ["tweet_id"],
    },
  },
  // List accounts
  {
    name: "list_accounts",
    description: "List all configured Twitter accounts",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

// Register tools with the server
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema,
    })),
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request: CallToolRequest) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "post_tweet": {
        const client = getAccountClient(args?.account as string | undefined);
        const tweet = await client.postTweet(args!.text as string);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  success: true,
                  tweet_id: tweet.id,
                  text: tweet.text,
                  created_at: tweet.created_at,
                  url: `https://twitter.com/i/web/status/${tweet.id}`,
                },
                null,
                2
              ),
            },
          ],
        };
      }

      case "reply_to_tweet": {
        const client = getAccountClient(args?.account as string | undefined);
        const tweet = await client.replyToTweet(
          args!.tweet_id as string,
          args!.text as string
        );
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  success: true,
                  tweet_id: tweet.id,
                  text: tweet.text,
                  created_at: tweet.created_at,
                  url: `https://twitter.com/i/web/status/${tweet.id}`,
                },
                null,
                2
              ),
            },
          ],
        };
      }

      case "get_tweet": {
        const client = getAccountClient();
        const tweet = await client.getTweet(args!.tweet_id as string);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(tweet, null, 2),
            },
          ],
        };
      }

      case "search_tweets": {
        const client = getAccountClient();
        const results = await client.searchTweets(
          args!.query as string,
          args!.max_results as number
        );
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  count: results.data.length,
                  tweets: results.data.map((t) => ({
                    id: t.id,
                    text: t.text,
                    author_id: t.author_id,
                    created_at: t.created_at,
                    public_metrics: t.public_metrics,
                  })),
                },
                null,
                2
              ),
            },
          ],
        };
      }

      case "search_all_tweets": {
        const client = getAccountClient();
        const results = await client.searchAllTweets(
          args!.query as string,
          args!.max_results as number
        );
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  count: results.data.length,
                  tweets: results.data.map((t) => ({
                    id: t.id,
                    text: t.text,
                    author_id: t.author_id,
                    created_at: t.created_at,
                    public_metrics: t.public_metrics,
                  })),
                },
                null,
                2
              ),
            },
          ],
        };
      }

      case "get_user": {
        const client = getAccountClient();
        const user = await client.getUserByUsername(args!.username as string);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(user, null, 2),
            },
          ],
        };
      }

      case "get_user_tweets": {
        const client = getAccountClient();
        // First get the user ID from username
        const user = await client.getUserByUsername(args!.username as string);
        const tweets = await client.getUserTweets(
          user.id,
          args!.max_results as number
        );
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  user: user.username,
                  user_id: user.id,
                  count: tweets.data.length,
                  tweets: tweets.data.map((t) => ({
                    id: t.id,
                    text: t.text,
                    created_at: t.created_at,
                    public_metrics: t.public_metrics,
                  })),
                },
                null,
                2
              ),
            },
          ],
        };
      }

      case "retweet": {
        const client = getAccountClient(args?.account as string | undefined);
        await client.retweet(args!.tweet_id as string, args!.user_id as string);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: true,
                message: `Successfully retweeted tweet ${args!.tweet_id}`,
              }),
            },
          ],
        };
      }

      case "like_tweet": {
        const client = getAccountClient(args?.account as string | undefined);
        await client.likeTweet(args!.tweet_id as string, args!.user_id as string);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: true,
                message: `Successfully liked tweet ${args!.tweet_id}`,
              }),
            },
          ],
        };
      }

      case "delete_tweet": {
        const client = getAccountClient(args?.account as string | undefined);
        await client.deleteTweet(args!.tweet_id as string);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: true,
                message: `Successfully deleted tweet ${args!.tweet_id}`,
              }),
            },
          ],
        };
      }

      case "list_accounts": {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                accounts: clients.map((c) => ({
                  name: c.getAccountName(),
                })),
                default_account: clients[0]?.getAccountName(),
              }),
            },
          ],
        };
      }

      default:
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ error: `Unknown tool: ${name}` }),
            },
          ],
          isError: true,
        };
    }
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            error: error instanceof Error ? error.message : String(error),
          }),
        },
      ],
      isError: true,
    };
  }
});

// MCP endpoint handler using Express
app.all("/mcp", async (req: Request, res: Response) => {
  try {
    // Handle JSON body
    const body = req.body;
    
    // Determine the method based on request
    let response: unknown;
    
    if (body && body.method) {
      // This is a JSON-RPC request
      switch (body.method) {
        case "initialize":
          response = {
            jsonrpc: "2.0",
            id: body.id,
            result: {
              protocolVersion: "2025-03-26",
              capabilities: { tools: {} },
              serverInfo: { name: "twitter-mcp-server", version: "1.0.0" },
            },
          };
          break;
        case "tools/list":
          response = {
            jsonrpc: "2.0",
            id: body.id,
            result: {
              tools: tools.map((tool) => ({
                name: tool.name,
                description: tool.description,
                inputSchema: tool.inputSchema,
              })),
            },
          };
          break;
        case "tools/call":
          const toolResult = await handleToolCall(body.params);
          response = {
            jsonrpc: "2.0",
            id: body.id,
            result: toolResult,
          };
          break;
        default:
          response = {
            jsonrpc: "2.0",
            id: body.id,
            error: { code: -32601, message: "Method not found" },
          };
      }
    } else {
      response = { error: "Invalid request" };
    }
    
    res.json(response);
  } catch (error) {
    console.error("MCP handler error:", error);
    res.status(500).json({ error: "Internal server error" });
  }
});

// Helper function to handle tool calls
async function handleToolCall(params: { name?: string; arguments?: Record<string, unknown> }) {
  const { name, arguments: args } = params;
  
  if (!name) {
    return { content: [{ type: "text", text: JSON.stringify({ error: "No tool name provided" }) }], isError: true };
  }

  try {
    switch (name) {
      case "post_tweet": {
        const client = getAccountClient(args?.account as string | undefined);
        const tweet = await client.postTweet(args!.text as string);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: true,
                tweet_id: tweet.id,
                text: tweet.text,
                created_at: tweet.created_at,
                url: `https://twitter.com/i/web/status/${tweet.id}`,
              }, null, 2),
            },
          ],
        };
      }
      case "reply_to_tweet": {
        const client = getAccountClient(args?.account as string | undefined);
        const tweet = await client.replyToTweet(args!.tweet_id as string, args!.text as string);
        return {
          content: [{ type: "text", text: JSON.stringify({ success: true, tweet_id: tweet.id, text: tweet.text, created_at: tweet.created_at, url: `https://twitter.com/i/web/status/${tweet.id}` }, null, 2) }],
        };
      }
      case "get_tweet": {
        const client = getAccountClient();
        const tweet = await client.getTweet(args!.tweet_id as string);
        return { content: [{ type: "text", text: JSON.stringify(tweet, null, 2) }] };
      }
      case "search_tweets": {
        const client = getAccountClient();
        const results = await client.searchTweets(args!.query as string, args!.max_results as number);
        return { content: [{ type: "text", text: JSON.stringify({ count: results.data.length, tweets: results.data.map((t) => ({ id: t.id, text: t.text, author_id: t.author_id, created_at: t.created_at, public_metrics: t.public_metrics })) }, null, 2) }] };
      }
      case "search_all_tweets": {
        const client = getAccountClient();
        const results = await client.searchAllTweets(args!.query as string, args!.max_results as number);
        return { content: [{ type: "text", text: JSON.stringify({ count: results.data.length, tweets: results.data.map((t) => ({ id: t.id, text: t.text, author_id: t.author_id, created_at: t.created_at, public_metrics: t.public_metrics })) }, null, 2) }] };
      }
      case "get_user": {
        const client = getAccountClient();
        const user = await client.getUserByUsername(args!.username as string);
        return { content: [{ type: "text", text: JSON.stringify(user, null, 2) }] };
      }
      case "get_user_tweets": {
        const client = getAccountClient();
        const user = await client.getUserByUsername(args!.username as string);
        const tweets = await client.getUserTweets(user.id, args!.max_results as number);
        return { content: [{ type: "text", text: JSON.stringify({ user: user.username, user_id: user.id, count: tweets.data.length, tweets: tweets.data.map((t) => ({ id: t.id, text: t.text, created_at: t.created_at, public_metrics: t.public_metrics })) }, null, 2) }] };
      }
      case "retweet": {
        const client = getAccountClient(args?.account as string | undefined);
        await client.retweet(args!.tweet_id as string, args!.user_id as string);
        return { content: [{ type: "text", text: JSON.stringify({ success: true, message: `Successfully retweeted tweet ${args!.tweet_id}` }) }] };
      }
      case "like_tweet": {
        const client = getAccountClient(args?.account as string | undefined);
        await client.likeTweet(args!.tweet_id as string, args!.user_id as string);
        return { content: [{ type: "text", text: JSON.stringify({ success: true, message: `Successfully liked tweet ${args!.tweet_id}` }) }] };
      }
      case "delete_tweet": {
        const client = getAccountClient(args?.account as string | undefined);
        await client.deleteTweet(args!.tweet_id as string);
        return { content: [{ type: "text", text: JSON.stringify({ success: true, message: `Successfully deleted tweet ${args!.tweet_id}` }) }] };
      }
      case "list_accounts": {
        return { content: [{ type: "text", text: JSON.stringify({ accounts: clients.map((c) => ({ name: c.getAccountName() })), default_account: clients[0]?.getAccountName() }) }] };
      }
      default:
        return { content: [{ type: "text", text: JSON.stringify({ error: `Unknown tool: ${name}` }) }], isError: true };
    }
  } catch (error) {
    return { content: [{ type: "text", text: JSON.stringify({ error: error instanceof Error ? error.message : String(error) }) }], isError: true };
  }
}

// Start the server
const PORT = config.port;
const HOST = config.host;

app.listen(PORT, HOST, () => {
  console.log(`🚀 Twitter MCP Server running on ${HOST}:${PORT}`);
  console.log(`📡 MCP endpoint: http://${HOST}:${PORT}/mcp`);
  console.log(`❤️  Health check: http://${HOST}:${PORT}/health`);
  console.log(
    `👤 Configured accounts: ${clients.map((c) => c.getAccountName()).join(", ")}`
  );
});

// Graceful shutdown
process.on("SIGTERM", () => {
  console.log("Shutting down...");
  process.exit(0);
});