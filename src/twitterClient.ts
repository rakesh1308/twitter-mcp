import type { Tweet, TwitterUser, SearchResponse } from "./types.js";
import type { TwitterAccount } from "./config.js";

const TWITTER_API_BASE = "https://api.twitter.com/2";

export class TwitterClient {
  private account: TwitterAccount;

  constructor(account: TwitterAccount) {
    this.account = account;
  }

  // OAuth 1.0a signature generation
  private async generateOAuthSignature(
    method: string,
    url: string,
    params: Record<string, string>
  ): Promise<string> {
    const encoder = new TextEncoder();
    
    // Sort parameters
    const sortedParams = Object.keys(params)
      .sort()
      .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
      .join("&");

    const signatureBase = `${method.toUpperCase()}&${encodeURIComponent(url)}&${encodeURIComponent(sortedParams)}`;
    
    const key = `${encodeURIComponent(this.account.apiSecret)}&${encodeURIComponent(this.account.accessTokenSecret)}`;
    
    const cryptoKey = await crypto.subtle.importKey(
      "raw",
      encoder.encode(key),
      { name: "HMAC", hash: "SHA-1" },
      false,
      ["sign"]
    );
    
    const signature = await crypto.subtle.sign(
      "HMAC",
      cryptoKey,
      encoder.encode(signatureBase)
    );
    
    return btoa(String.fromCharCode(...new Uint8Array(signature)));
  }

  private async oauth1Request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    if (!this.account.accessToken || !this.account.accessTokenSecret) {
      throw new Error("OAuth 1.0a requires access token and secret.");
    }

    const method = (options.method || "GET").toUpperCase();
    const url = `${TWITTER_API_BASE}${endpoint}`;
    
    // Parse existing query params if any
    const urlObj = new URL(url);
    const queryParams: Record<string, string> = {};
    urlObj.searchParams.forEach((value, key) => {
      queryParams[key] = value;
    });

    // OAuth 1.0a parameters
    const oauthParams: Record<string, string> = {
      oauth_consumer_key: this.account.apiKey,
      oauth_nonce: Math.random().toString(36).substring(2) + Date.now().toString(36),
      oauth_signature_method: "HMAC-SHA1",
      oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
      oauth_token: this.account.accessToken,
      oauth_version: "1.0",
    };

    // Combine all params for signature
    const allParams = { ...queryParams, ...oauthParams };
    const signature = await this.generateOAuthSignature(method, url, allParams);
    oauthParams.oauth_signature = signature;

    // Build Authorization header
    const authHeader =
      "OAuth " +
      Object.keys(oauthParams)
        .map((k) => `${encodeURIComponent(k)}="${encodeURIComponent(oauthParams[k])}"`)
        .join(", ");

    const response = await fetch(url, {
      ...options,
      headers: {
        Authorization: authHeader,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        `Twitter API error: ${response.status} - ${error.detail || response.statusText}`
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

  // Upload media (returns media ID) using OAuth 1.0a
  async uploadMedia(base64Data: string): Promise<string> {
    const binaryData = Buffer.from(base64Data, "base64");
    
    // For media upload, we use OAuth 1.0a with binary data
    const method = "POST";
    const url = `${TWITTER_API_BASE}/media/upload`;
    
    const oauthParams: Record<string, string> = {
      oauth_consumer_key: this.account.apiKey,
      oauth_nonce: Math.random().toString(36).substring(2) + Date.now().toString(36),
      oauth_signature_method: "HMAC-SHA1",
      oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
      oauth_token: this.account.accessToken,
      oauth_version: "1.0",
    };

    const signature = await this.generateOAuthSignature(method, url, oauthParams);
    oauthParams.oauth_signature = signature;

    const authHeader =
      "OAuth " +
      Object.keys(oauthParams)
        .map((k) => `${encodeURIComponent(k)}="${encodeURIComponent(oauthParams[k])}"`)
        .join(", ");

    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: authHeader,
        "Content-Type": "application/octet-stream",
      },
      body: binaryData,
    });

    if (!response.ok) {
      throw new Error(`Media upload failed: ${response.statusText}`);
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