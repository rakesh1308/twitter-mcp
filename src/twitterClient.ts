import type { Tweet, TwitterUser, SearchResponse } from "./types.js";
import type { TwitterAccount } from "./config.js";

const TWITTER_API_BASE = "https://api.twitter.com/2";

export class TwitterClient {
  private account: TwitterAccount;

  constructor(account: TwitterAccount) {
    this.account = account;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.account.bearerToken}`,
      "Content-Type": "application/json",
    };

    // Add user context headers if available (OAuth 1.0a style for write operations)
    if (this.account.accessToken) {
      headers["X-Access-Token"] = this.account.accessToken;
    }

    const response = await fetch(`${TWITTER_API_BASE}${endpoint}`, {
      ...options,
      headers: { ...headers, ...(options.headers as Record<string, string>) },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        `Twitter API error: ${response.status} - ${
          error.detail || response.statusText
        }`
      );
    }

    return response.json() as Promise<T>;
  }

  // Post a new tweet
  async postTweet(text: string): Promise<Tweet> {
    const result = await this.request<{ data: Tweet }>("/tweets", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    return result.data;
  }

  // Reply to a tweet
  async replyToTweet(tweetId: string, text: string): Promise<Tweet> {
    const result = await this.request<{ data: Tweet }>("/tweets", {
      method: "POST",
      body: JSON.stringify({
        text,
        reply: { in_reply_to_tweet_id: tweetId },
      }),
    });
    return result.data;
  }

  // Retweet a tweet
  async retweet(tweetId: string, userId: string): Promise<void> {
    await this.request(`/users/${userId}/retweets`, {
      method: "POST",
      body: JSON.stringify({ tweet_id: tweetId }),
    });
  }

  // Like a tweet
  async likeTweet(tweetId: string, userId: string): Promise<void> {
    await this.request(`/users/${userId}/likes`, {
      method: "POST",
      body: JSON.stringify({ tweet_id: tweetId }),
    });
  }

  // Get a tweet by ID
  async getTweet(tweetId: string): Promise<Tweet> {
    const result = await this.request<{ data: Tweet }>(
      `/tweets/${tweetId}?expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`
    );
    return result.data;
  }

  // Search recent tweets
  async searchTweets(
    query: string,
    maxResults: number = 10
  ): Promise<SearchResponse> {
    const result = await this.request<SearchResponse>(
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
    const result = await this.request<SearchResponse>(
      `/tweets/search/all?query=${encodeURIComponent(
        query
      )}&max_results=${maxResults}&expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`
    );
    return result;
  }

  // Get user by username
  async getUserByUsername(username: string): Promise<TwitterUser> {
    const result = await this.request<{ data: TwitterUser }>(
      `/users/by/username/${username}?user.fields=created_at,description,public_metrics,profile_image_url,verified,url`
    );
    return result.data;
  }

  // Get user by ID
  async getUserById(userId: string): Promise<TwitterUser> {
    const result = await this.request<{ data: TwitterUser }>(
      `/users/${userId}?user.fields=created_at,description,public_metrics,profile_image_url,verified,url`
    );
    return result.data;
  }

  // Get user's tweets
  async getUserTweets(
    userId: string,
    maxResults: number = 10
  ): Promise<{ data: Tweet[]; meta: { result_count: number; next_token?: string } }> {
    const result = await this.request<{
      data: Tweet[];
      meta: { result_count: number; next_token?: string };
    }>(
      `/users/${userId}/tweets?max_results=${maxResults}&expansions=author_id,referenced_tweets.id,attachments.media_keys&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`
    );
    return result;
  }

  // Delete a tweet
  async deleteTweet(tweetId: string): Promise<void> {
    await this.request(`/tweets/${tweetId}`, { method: "DELETE" });
  }

  // Upload media (returns media ID)
  async uploadMedia(base64Data: string): Promise<string> {
    const binaryData = Buffer.from(base64Data, "base64");
    const response = await fetch(`${TWITTER_API_BASE}/media/upload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.account.bearerToken}`,
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

  // Post tweet with media
  async postTweetWithMedia(text: string, mediaIds: string[]): Promise<Tweet> {
    const result = await this.request<{ data: Tweet }>("/tweets", {
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