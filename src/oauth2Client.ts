import * as fs from "fs";
import * as path from "path";
import type { TwitterUser } from "./types.js";

const TOKEN_URL = "https://api.twitter.com/2/oauth2/token";

export interface OAuth2Tokens {
  clientId: string;
  clientSecret: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  scope?: string;
}

interface Options {
  refreshSkewSeconds: number;
  tokenFile: string;
}

export class OAuth2Client {
  private tokens: OAuth2Tokens;
  private readonly opts: Options;
  private inflightRefresh: Promise<OAuth2Tokens> | null = null;

  private constructor(tokens: OAuth2Tokens, opts: Options) {
    this.tokens = tokens;
    this.opts = opts;
  }

  static fromEnv(): OAuth2Client | null {
    const clientId = process.env.TWITTER_OAUTH2_CLIENT_ID;
    const clientSecret = process.env.TWITTER_OAUTH2_CLIENT_SECRET;
    const accessToken = process.env.TWITTER_OAUTH2_ACCESS_TOKEN;
    const refreshToken = process.env.TWITTER_OAUTH2_REFRESH_TOKEN;
    if (!clientId || !clientSecret || !accessToken || !refreshToken) return null;

    const opts: Options = {
      refreshSkewSeconds: Number(process.env.OAUTH2_REFRESH_SKEW_SECONDS || 60),
      tokenFile: process.env.TWITTER_OAUTH2_TOKEN_FILE || "/data/oauth2.json",
    };
    const client = new OAuth2Client(
      {
        clientId,
        clientSecret,
        accessToken,
        refreshToken,
        expiresAt: parseExpires(process.env.TWITTER_OAUTH2_EXPIRES_AT),
        scope: process.env.TWITTER_OAUTH2_SCOPE,
      },
      opts,
    );
    client.loadOrSeed();
    return client;
  }

  private loadOrSeed(): void {
    try {
      if (fs.existsSync(this.opts.tokenFile)) {
        const stored = JSON.parse(fs.readFileSync(this.opts.tokenFile, "utf8")) as OAuth2Tokens;
        if (stored.accessToken && stored.refreshToken) {
          this.tokens = { ...this.tokens, ...stored, clientId: this.tokens.clientId, clientSecret: this.tokens.clientSecret };
          console.log(`[oauth2] loaded tokens from ${this.opts.tokenFile}`);
          return;
        }
      }
    } catch (err) {
      console.error("[oauth2] failed to load token file:", err);
    }
    this.persist();
  }

  private persist(): void {
    try {
      const dir = path.dirname(this.opts.tokenFile);
      fs.mkdirSync(dir, { recursive: true });
      const tmp = `${this.opts.tokenFile}.tmp`;
      fs.writeFileSync(tmp, JSON.stringify(this.tokens, null, 2), { mode: 0o600 });
      fs.renameSync(tmp, this.opts.tokenFile);
      try { fs.chmodSync(this.opts.tokenFile, 0o600); } catch { /* best-effort */ }
    } catch (err) {
      console.error("[oauth2] persist failed:", err);
    }
  }

  private isExpired(): boolean {
    return this.tokens.expiresAt * 1000 - Date.now() < this.opts.refreshSkewSeconds * 1000;
  }

  async getValidAccessToken(): Promise<string> {
    if (this.isExpired()) await this.refresh();
    return this.tokens.accessToken;
  }

  async refresh(): Promise<OAuth2Tokens> {
    if (this.inflightRefresh) return this.inflightRefresh;
    this.inflightRefresh = this.doRefresh().finally(() => { this.inflightRefresh = null; });
    return this.inflightRefresh;
  }

  private async doRefresh(): Promise<OAuth2Tokens> {
    const body = new URLSearchParams({ grant_type: "refresh_token", refresh_token: this.tokens.refreshToken });
    const auth = Buffer.from(`${this.tokens.clientId}:${this.tokens.clientSecret}`).toString("base64");
    const res = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { Authorization: `Basic ${auth}`, "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) throw new Error(`OAuth2 refresh failed: ${res.status} ${await res.text()}`);
    const json: any = await res.json();
    this.tokens = {
      clientId: this.tokens.clientId,
      clientSecret: this.tokens.clientSecret,
      accessToken: json.access_token,
      refreshToken: json.refresh_token ?? this.tokens.refreshToken,
      expiresAt: Math.floor(Date.now() / 1000) + Number(json.expires_in || 7200),
      scope: json.scope ?? this.tokens.scope,
    };
    this.persist();
    return this.tokens;
  }

  async fetch<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
    const send = async () => {
      await this.getValidAccessToken();
      const headers = new Headers(init.headers || {});
      headers.set("Authorization", `Bearer ${this.tokens.accessToken}`);
      if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
      const res = await fetch(`https://api.twitter.com/2${endpoint}`, { ...init, headers });
      if (res.status === 401) {
        await this.refresh();
        headers.set("Authorization", `Bearer ${this.tokens.accessToken}`);
        const retry = await fetch(`https://api.twitter.com/2${endpoint}`, { ...init, headers });
        if (!retry.ok) throw await toApiError(retry);
        if (retry.status === 204) return {} as T;
        return (await retry.json()) as T;
      }
      if (!res.ok) throw await toApiError(res);
      if (res.status === 204) return {} as T;
      return (await res.json()) as T;
    };
    return send();
  }

  async followUser(myUserId: string, targetUserId: string): Promise<void> {
    await this.fetch(`/users/${myUserId}/following`, {
      method: "POST",
      body: JSON.stringify({ target_user_id: targetUserId }),
    });
  }

  async unfollowUser(myUserId: string, targetUserId: string): Promise<void> {
    await this.fetch(`/users/${myUserId}/following/${targetUserId}`, { method: "DELETE" });
  }

  async getFollowing(
    myUserId: string,
    maxResults: number = 100,
    paginationToken?: string,
  ): Promise<{ data: TwitterUser[]; meta: { result_count: number; next_token?: string } }> {
    const params = new URLSearchParams({ max_results: String(maxResults) });
    if (paginationToken) params.set("pagination_token", paginationToken);
    params.set("user.fields", "id,name,username,description,public_metrics,verified,profile_image_url");
    return this.fetch(`/users/${myUserId}/following?${params.toString()}`);
  }

  async getFollowers(
    myUserId: string,
    maxResults: number = 100,
    paginationToken?: string,
  ): Promise<{ data: TwitterUser[]; meta: { result_count: number; next_token?: string } }> {
    const params = new URLSearchParams({ max_results: String(maxResults) });
    if (paginationToken) params.set("pagination_token", paginationToken);
    params.set("user.fields", "id,name,username,description,public_metrics,verified,profile_image_url");
    return this.fetch(`/users/${myUserId}/followers?${params.toString()}`);
  }
}

function parseExpires(raw: string | undefined): number {
  if (!raw) return Math.floor(Date.now() / 1000);
  const trimmed = raw.trim();
  if (/^\d+$/.test(trimmed)) {
    const n = Number(trimmed);
    return n > 1e12 ? Math.floor(n / 1000) : n;
  }
  const ts = Date.parse(trimmed);
  return Number.isNaN(ts) ? Math.floor(Date.now() / 1000) : Math.floor(ts / 1000);
}

async function toApiError(res: Response): Promise<Error> {
  const text = await res.text();
  let detail = res.statusText;
  try {
    const j = JSON.parse(text);
    detail = j.detail || j.error || j.title || detail;
  } catch { detail = text || detail; }
  const err: any = new Error(`Twitter API error: ${res.status} - ${detail}`);
  err.status = res.status;
  return err;
}