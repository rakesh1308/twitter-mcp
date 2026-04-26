import { z } from "zod";

export const TwitterAccountSchema = z.object({
  name: z.string().describe("Account name/identifier"),
  apiKey: z.string().describe("Twitter API Key (from Keys and tokens)"),
  apiSecret: z.string().describe("Twitter API Secret Key"),
  accessToken: z.string().describe("User Access Token"),
  accessTokenSecret: z.string().describe("User Access Token Secret"),
});

export const ConfigSchema = z.object({
  accounts: z.array(TwitterAccountSchema).min(1),
  port: z.number().default(3000),
  host: z.string().default("0.0.0.0"),
});

export type TwitterAccount = z.infer<typeof TwitterAccountSchema>;
export type Config = z.infer<typeof ConfigSchema>;

export function loadConfig(): Config {
  const accounts: TwitterAccount[] = [];

  // Load Account 1
  const account1Name = process.env.ACCOUNT1_NAME || "Account 1";
  const account1ApiKey = process.env.ACCOUNT1_API_KEY;
  const account1ApiSecret = process.env.ACCOUNT1_API_SECRET;
  const account1AccessToken = process.env.ACCOUNT1_ACCESS_TOKEN;
  const account1AccessSecret = process.env.ACCOUNT1_ACCESS_TOKEN_SECRET;

  if (account1ApiKey && account1ApiSecret && account1AccessToken && account1AccessSecret) {
    accounts.push({
      name: account1Name,
      apiKey: account1ApiKey,
      apiSecret: account1ApiSecret,
      accessToken: account1AccessToken,
      accessTokenSecret: account1AccessSecret,
    });
  }

  if (accounts.length === 0) {
    throw new Error(
      "No Twitter accounts configured. Please set ACCOUNT1_API_KEY, ACCOUNT1_API_SECRET, ACCOUNT1_ACCESS_TOKEN, and ACCOUNT1_ACCESS_TOKEN_SECRET environment variables."
    );
  }

  return {
    accounts,
    port: parseInt(process.env.PORT || "3000", 10),
    host: process.env.HOST || "0.0.0.0",
  };
}