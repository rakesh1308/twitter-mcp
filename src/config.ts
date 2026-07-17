export interface TwitterAccount {
  name: string;
  apiKey: string;
  apiSecret: string;
  accessToken: string;
  accessTokenSecret: string;
}

export interface Config {
  account: TwitterAccount;
  port: number;
  host: string;
}

export function loadConfig(): Config {
  const apiKey = process.env.TWITTER_API_KEY;
  const apiSecret = process.env.TWITTER_API_SECRET;
  const accessToken = process.env.TWITTER_ACCESS_TOKEN;
  const accessTokenSecret = process.env.TWITTER_ACCESS_TOKEN_SECRET;

  if (!apiKey || !apiSecret || !accessToken || !accessTokenSecret) {
    throw new Error(
      "Missing required env vars: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET.",
    );
  }

  return {
    account: {
      name: process.env.ACCOUNT_NAME || "Twitter Account",
      apiKey,
      apiSecret,
      accessToken,
      accessTokenSecret,
    },
    port: Number(process.env.PORT || 3000),
    host: process.env.HOST || "0.0.0.0",
  };
}