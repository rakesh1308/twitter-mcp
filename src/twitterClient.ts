import OAuth from "oauth-1.0a";
import * as crypto from "crypto";
import type { Tweet, TwitterUser, SearchResponse } from "./types.js";
import type { TwitterAccount } from "./config.js";

const TWITTER_API_BASE = "https://api.twitter.com/2";
const DEFAULT_PAGE_SIZE = 10;

export class TwitterClient {
  private readonly account: TwitterAccount;
  private readonly oauth: OAuth;

  constructor(account: TwitterAccount) {
    this.account = account;
    this.oauth = new OAuth({
      consumer: { key: account.apiKey, secret: account.apiSecret },
      signature_method: "HMAC-SHA1",
      hash_function: (baseString: string, key: string) =>
        crypto.createHmac("sha1", key).update(baseString).digest("base64"),
    });
  }

  getAccountName(): string {
    return this.account.name;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    if (!this.account.accessToken || !this.account.accessTokenSecret) {
      throw new Error("OAuth 1.0a requires access token and secret.");
    }
    const url = `${TWITTER_API_BASE}${endpoint}`;
    const method = (options.method || "GET").toUpperCase() as "GET" | "POST" | "PUT" | "DELETE";

    const urlObj = new URL(url);
    const queryData: Record<string, string> = {};
    urlObj.searchParams.forEach((v, k) => { queryData[k] = v; });

    const authHeader = this.oauth.toHeader(
      this.oauth.authorize(
        { url: urlObj.origin + urlObj.pathname, method, data: queryData },
        { key: this.account.accessToken, secret: this.account.accessTokenSecret },
      ),
    );

    const response = await fetch(url, {
      ...options,
      method,
      headers: {
        Authorization: authHeader.Authorization,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      const text = await response.text();
      let detail = response.statusText;
      try {
        const j = JSON.parse(text);
        detail = j.detail || j.error || detail;
      } catch { detail = text || detail; }
      const err: any = new Error(`Twitter API error: ${response.status} - ${detail}`);
      err.status = response.status;
      err.headers = response.headers;
      throw err;
    }
    if (response.status === 204) return {} as T;
    return (await response.json()) as T;
  }

  async postTweet(text: string): Promise<Tweet> {
    const r = await this.request<{ data: Tweet }>("/tweets", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    return r.data;
  }

  async replyToTweet(tweetId: string, text: string): Promise<Tweet> {
    const r = await this.request<{ data: Tweet }>("/tweets", {
      method: "POST",
      body: JSON.stringify({ text, reply: { in_reply_to_tweet_id: tweetId } }),
    });
    return r.data;
  }

  async retweet(tweetId: string, userId: string): Promise<void> {
    await this.request(`/users/${userId}/retweets`, {
      method: "POST",
      body: JSON.stringify({ tweet_id: tweetId }),
    });
  }

  async likeTweet(tweetId: string, userId: string): Promise<void> {
    await this.request(`/users/${userId}/likes`, {
      method: "POST",
      body: JSON.stringify({ tweet_id: tweetId }),
    });
  }

  async getTweet(tweetId: string): Promise<Tweet> {
    const r = await this.request<{ data: Tweet }>(
      `/tweets/${tweetId}?expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`,
    );
    return r.data;
  }

  async searchTweets(query: string, maxResults: number = DEFAULT_PAGE_SIZE): Promise<SearchResponse> {
    return this.request<SearchResponse>(
      `/tweets/search/recent?query=${encodeURIComponent(query)}&max_results=${maxResults}&expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`,
    );
  }

  async searchAllTweets(query: string, maxResults: number = DEFAULT_PAGE_SIZE): Promise<SearchResponse> {
    return this.request<SearchResponse>(
      `/tweets/search/all?query=${encodeURIComponent(query)}&max_results=${maxResults}&expansions=author_id,referenced_tweets.id,attachments.media_keys&user.fields=name,username,profile_image_url&tweet.fields=created_at,public_metrics,conversation_id,in_reply_to_user_id&media.fields=url,preview_image_url`,
    );
  }

  async getUserByUsername(username: string): Promise<TwitterUser> {
    const r = await this.request<{ data: TwitterUser }>(
      `/users/by/username/${username}?user.fields=created_at,description,public_metrics,profile_image_url,verified,url`,
    );
    return r.data;
  }

  async getMe(): Promise<TwitterUser> {
    const r = await this.request<{ data: TwitterUser }>(
      `/users/me?user.fields=id,username,name,created_at`,
    );
    return r.data;
  }

  async getUserTweets(
    userId: string,
    maxResults: number = 100,
    paginationToken?: string,
  ): Promise<{ data: Tweet[]; meta: { result_count: number; next_token?: string } }> {
    const params = new URLSearchParams({ max_results: String(maxResults) });
    if (paginationToken) params.set("pagination_token", paginationToken);
    return this.request(`/users/${userId}/tweets?${params.toString()}`);
  }

  async deleteTweet(tweetId: string): Promise<void> {
    await this.request(`/tweets/${tweetId}`, { method: "DELETE" });
  }

  async uploadMedia(base64Data: string): Promise<string> {
    const url = `${TWITTER_API_BASE}/media/upload`;
    const authHeader = this.oauth.toHeader(
      this.oauth.authorize(
        { url, method: "POST" },
        { key: this.account.accessToken, secret: this.account.accessTokenSecret },
      ),
    );
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: authHeader.Authorization,
        "Content-Type": "application/octet-stream",
      },
      body: Buffer.from(base64Data, "base64"),
    });
    if (!response.ok) {
      throw new Error(`Media upload failed: ${response.status} - ${await response.text()}`);
    }
    return (await response.json() as { media_id_string: string }).media_id_string;
  }
}