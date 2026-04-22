import OAuth from "oauth-1.0a";
import * as crypto from "crypto";
import type { Tweet, TwitterUser, SearchResponse } from "./types.js";
import type { TwitterAccount } from "./config.js";

const TWITTER_API_BASE = "https://api.twitter.com/2";

export class TwitterClient {
  private account: TwitterAccount;
  private oauth: OAuth;

  constructor(account: TwitterAccount) {
    this.account = account;
    
    // Initialize OAuth 1.0a with the account credentials
    this.oauth = new OAuth({
      consumer: {
        key: this.account.apiKey,
        secret: this.account.apiSecret,
      },
      signature_method: "HMAC-SHA1",
      hash_function: (baseString: string, key: string) => {
        // Use Node.js crypto for HMAC-SHA1
        const hmac = crypto.createHmac("sha1", key);
        hmac.update(baseString);
        return hmac.digest("base64");
      },
    });
    
    console.log(`[TwitterClient] Initialized for account: ${account.name}`);
    console.log(`[TwitterClient] API Key: ${account.apiKey.substring(0, 10)}...`);
    console.log(`[TwitterClient] Access Token: ${account.accessToken.substring(0, 20)}...`);
  }

  private async oauth1Request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    if (!this.account.accessToken || !this.account.accessTokenSecret) {
      throw new Error("OAuth 1.0a requires access token and secret.");
    }

    const url = `${TWITTER_API_BASE}${endpoint}`;
    const method = (options.method || "GET").toUpperCase() as "GET" | "POST" | "PUT" | "DELETE";
    
    console.log(`[OAuth Request] ${method} ${url}`);
    
    // Parse query parameters from URL
    const urlObj = new URL(url);
    const queryData: Record<string, string> = {};
    urlObj.searchParams.forEach((value, key) => {
      queryData[key] = value;
    });

    // Generate OAuth authorization header
    const authData = {
      url: urlObj.origin + urlObj.pathname + (urlObj.search ? urlObj.search : ""),
      method: method,
    };
    
    const token = {
      key: this.account.accessToken,
      secret: this.account.accessTokenSecret,
    };
    
    console.log(`[OAuth] Auth URL: ${authData.url}`);
    console.log(`[OAuth] Token Key: ${token.key.substring(0, 20)}...`);
    
    const authHeader = this.oauth.authorize(authData, token);
    const headerAuth = this.oauth.toHeader(authHeader);
    
    console.log(`[OAuth] Authorization: ${headerAuth.Authorization.substring(0, 50)}...`);

    const response = await fetch(url, {
      ...options,
      method: method,
      headers: {
        Authorization: headerAuth.Authorization,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    console.log(`[OAuth Response] Status: ${response.status}`);

    if (!response.ok) {
      const errorText = await response.text();
      let errorDetail = response.statusText;
      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorJson.error || errorDetail;
      } catch {
        // Use raw text if not JSON
        errorDetail = errorText || errorDetail;
      }
      console.log(`[OAuth Error] ${response.status} - ${errorDetail}`);
      throw new Error(
        `Twitter API error: ${response.status} - ${errorDetail}`
      );
    }

    // Handle 204 No Content responses
    if (response.status === 204) {
      return {} as T;
    }

    return response.json() as Promise<T>;
  }

  // Post a new tweet using OAuth 1.0a
  async postTweet(text: string): Promise<Tweet> {
    console.log(`[postTweet] Posting: "${text}"`);
    const result = await this.oauth1Request<{ data: Tweet }>("/tweets", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    return result.data;
  }

  // Reply to a tweet using OAuth 1.0a
  async replyToTweet(tweetId: string, text: string): Promise<Tweet> {
    const result = await this.oauth1Request<{ data: Tweet }>("/tweets", {
      method: "POST",
      body: JSON.stringify({
        text,
        reply: { in_reply_to_tweet_id: tweetId },
      }),
    });
    return result.data;
  }

  // Retweet a tweet using OAuth 1.0a
  async retweet(tweetId: string, userId: string): Promise<void> {
    await this.oauth1Request(`/users/${userId}/retweets`, {
      method: "POST",
      body: JSON.stringify({ tweet_id: tweetId }),
    });
  }

  // Like a tweet using OAuth 1.0a
  async likeTweet(tweetId: string, userId: string): Promise<void> {
    await this.oauth1Request(`/users/${userId}/likes`, {
      method: "POST",
      body: JSON.stringify({ tweet_id: tweetId }),
    });
  }

  // Get a tweet by ID
  async getTweet(tweetId: string): Promise<Tweet> {
    const result = await this.oauth1Request<{ data: Tweet }>(
      `/tweets/${tweetId}?expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`
    );
    return result.data;
  }

  // Search recent tweets
  async searchTweets(
    query: string,
    maxResults: number = 10
  ): Promise<SearchResponse> {
    const result = await this.oauth1Request<SearchResponse>(
      `/tweets/search/recent?query=${encodeURIComponent(
        query
      )}&max_results=${maxResults}&expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`
    );
    return result;
  }

  // Search all tweets (requires elevated access)
  async searchAllTweets(
    query: string,
    maxResults: number = 10
  ): Promise<SearchResponse> {
    const result = await this.oauth1Request<SearchResponse>(
      `/tweets/search/all?query=${encodeURIComponent(
        query
      )}&max_results=${maxResults}&expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`
    );
    return result;
  }

  // Get user by username
  async getUserByUsername(username: string): Promise<TwitterUser> {
    const result = await this.oauth1Request<{ data: TwitterUser }>(
      `/users/by/username/${username}?user.fields=created_at,description,public_metrics,profile_image_url,verified,url`
    );
    return result.data;
  }

  // Get user by ID
  async getUserById(userId: string): Promise<TwitterUser> {
    const result = await this.oauth1Request<{ data: TwitterUser }>(
      `/users/${userId}?user.fields=created_at,description,public_metrics,profile_image_url,verified,url`
    );
    return result.data;
  }

  // Get user's tweets
  async getUserTweets(
    userId: string,
    maxResults: number = 10
  ): Promise<{ data: Tweet[]; meta: { result_count: number; next_token?: string } }> {
    const result = await this.oauth1Request<{
      data: Tweet[];
      meta: { result_count: number; next_token?: string };
    }>(
      `/users/${userId}/tweets?max_results=${maxResults}&expansions=author_id,referenced_tweets.id,attachments.media_keys&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`
    );
    return result;
  }

  // Delete a tweet using OAuth 1.0a
  async deleteTweet(tweetId: string): Promise<void> {
    await this.oauth1Request(`/tweets/${tweetId}`, { method: "DELETE" });
  }

  // Upload media (returns media ID)
  async uploadMedia(base64Data: string): Promise<string> {
    const binaryData = Buffer.from(base64Data, "base64");
    
    const url = `${TWITTER_API_BASE}/media/upload`;
    const method = "POST";
    
    const authHeader = this.oauth.authorize(
      { url, method },
      {
        key: this.account.accessToken,
        secret: this.account.accessTokenSecret,
      }
    );

    const response = await fetch(url, {
      method: method,
      headers: {
        Authorization: this.oauth.toHeader(authHeader).Authorization,
        "Content-Type": "application/octet-stream",
      },
      body: binaryData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Media upload failed: ${response.status} - ${errorText}`);
    }

    const result = await response.json() as { media_id_string: string };
    return result.media_id_string;
  }

  // Post tweet with media using OAuth 1.0a
  async postTweetWithMedia(text: string, mediaIds: string[]): Promise<Tweet> {
    const result = await this.oauth1Request<{ data: Tweet }>("/tweets", {
      method: "POST",
      body: JSON.stringify({
        text,
        media: { media_ids: mediaIds },
      }),
    });
    return result.data;
  }

  getAccountName(): string {
    return this.account.name;
  }
}