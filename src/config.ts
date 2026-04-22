import { z } from "zod";

export const TwitterAccountSchema = z.object({
  name: z.string().describe("Account name/identifier"),
  bearerToken: z.string().describe("Twitter API Bearer Token"),
  accessToken: z.string().optional().describe("User Access Token (for user context)"),
  accessTokenSecret: z.string().optional().describe("User Access Token Secret"),
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
  const account1Bearer = process.env.ACCOUNT1_BEARER_TOKEN;
  const account1AccessToken = process.env.ACCOUNT1_ACCESS_TOKEN;
  const account1AccessSecret = process.env.ACCOUNT1_ACCESS_TOKEN_SECRET;

  if (account1Bearer) {
    accounts.push({
      name: account1Name,
      bearerToken: account1Bearer,
      accessToken: account1AccessToken,
      accessTokenSecret: account1AccessSecret,
    });
  }

  // Load Account 2
  const account2Name = process.env.ACCOUNT2_NAME || "Account 2";
  const account2Bearer = process.env.ACCOUNT2_BEARER_TOKEN;
  const account2AccessToken = process.env.ACCOUNT2_ACCESS_TOKEN;
  const account2AccessSecret = process.env.ACCOUNT2_ACCESS_TOKEN_SECRET;

  if (account2Bearer) {
    accounts.push({
      name: account2Name,
      bearerToken: account2Bearer,
      accessToken: account2AccessToken,
      accessTokenSecret: account2AccessSecret,
    });
  }

  if (accounts.length === 0) {
    throw new Error(
      "No Twitter accounts configured. Please set at least ACCOUNT1_BEARER_TOKEN environment variable."
    );
  }

  return {
    accounts,
    port: parseInt(process.env.PORT || "3000", 10),
    host: process.env.HOST || "0.0.0.0",
  };
}