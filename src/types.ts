export interface Tweet {
  id: string;
  text: string;
  author_id: string;
  created_at: string;
  conversation_id?: string;
  in_reply_to_user_id?: string;
  referenced_tweets?: Array<{
    id: string;
    type: "retweeted" | "replied_to" | "quoted";
  }>;
  public_metrics?: {
    retweet_count: number;
    reply_count: number;
    like_count: number;
    quote_count: number;
  };
  attachments?: {
    media_keys?: string[];
  };
}

export interface TwitterUser {
  id: string;
  name: string;
  username: string;
  created_at?: string;
  description?: string;
  public_metrics?: {
    followers_count: number;
    following_count: number;
    tweet_count: number;
    listed_count: number;
  };
  profile_image_url?: string;
  url?: string;
  verified?: boolean;
}

export interface SearchResponse {
  data: Tweet[];
  meta: {
    result_count: number;
    next_token?: string;
    previous_token?: string;
  };
}

export interface ApiError {
  title: string;
  detail: string;
  type: string;
}