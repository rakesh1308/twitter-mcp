"""Declarative X API v2 endpoint and MCP tool catalog.

Every tool is described here as data: HTTP method, path template, auth mode,
parameter list and JSON body fields. The server builds MCP input schemas and
request payloads from these definitions, so no endpoint path is ever
interpolated by hand into a URL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Auth modes:
#   "oauth1" - OAuth 1.0a user context (always configured)
#   "oauth2" - OAuth 2.0 user context (media / DM / Chat / Spaces families)
#   "auto"   - try the primary transport, fall back to the other on 401/403


@dataclass(frozen=True)
class Param:
    name: str
    type: str = "string"
    required: bool = False
    description: str = ""
    default: Any = None
    minimum: int | None = None
    maximum: int | None = None
    enum: tuple[str, ...] | None = None
    api_name: str | None = None


@dataclass(frozen=True)
class Tool:
    name: str
    method: str
    path: str
    description: str
    family: str = "General"
    auth: str = "oauth1"
    params: tuple[Param, ...] = ()
    body_params: tuple[str, ...] = ()
    output: str = "json"
    scopes: tuple[str, ...] = ()

    @property
    def path_params(self) -> tuple[str, ...]:
        names: list[str] = []
        chunk = self.path
        while "{" in chunk and "}" in chunk:
            start = chunk.index("{")
            end = chunk.index("}", start)
            names.append(chunk[start + 1 : end])
            chunk = chunk[end + 1 :]
        return tuple(names)


def P(
    name: str,
    type: str = "string",
    *,
    required: bool = False,
    desc: str = "",
    default: Any = None,
    minimum: int | None = None,
    maximum: int | None = None,
    enum: tuple[str, ...] | None = None,
    api_name: str | None = None,
) -> Param:
    return Param(
        name=name,
        type=type,
        required=required,
        description=desc,
        default=default,
        minimum=minimum,
        maximum=maximum,
        enum=enum,
        api_name=api_name,
    )


def T(
    name: str,
    method: str,
    path: str,
    desc: str,
    *,
    family: str = "General",
    auth: str = "oauth1",
    params: tuple[Param, ...] = (),
    body: tuple[str, ...] = (),
    output: str = "json",
    scopes: tuple[str, ...] = (),
) -> Tool:
    return Tool(
        name=name,
        method=method,
        path=path,
        description=desc,
        family=family,
        auth=auth,
        params=params,
        body_params=body,
        output=output,
        scopes=scopes,
    )


# --------------------------------------------------------------------------
# reusable parameter groups
# --------------------------------------------------------------------------

_DEFAULT_EXPANSIONS = "author_id,referenced_tweets.id,attachments.media_keys"
_DEFAULT_TWEET_FIELDS = "created_at,public_metrics,conversation_id,in_reply_to_user_id"
_DEFAULT_USER_FIELDS = "name,username,profile_image_url"
_DEFAULT_MEDIA_FIELDS = "url,preview_image_url"


def paging(default: int = 10, maximum: int = 100) -> tuple[Param, ...]:
    return (
        P("max_results", "integer", desc="Number of results per page.", default=default, minimum=1, maximum=maximum),
        P("pagination_token", "string", desc="Token returned by a previous call for the next page."),
    )


def fields(
    *,
    tweet: bool = True,
    user: bool = True,
    media: bool = True,
    expansions: bool = True,
    defaults: bool = False,
) -> tuple[Param, ...]:
    out: list[Param] = []
    if tweet:
        out.append(
            P(
                "tweet_fields",
                "string",
                desc="Comma separated tweet.fields to return.",
                default=_DEFAULT_TWEET_FIELDS if defaults else None,
                api_name="tweet.fields",
            )
        )
    if user:
        out.append(
            P(
                "user_fields",
                "string",
                desc="Comma separated user.fields to return.",
                default=_DEFAULT_USER_FIELDS if defaults else None,
                api_name="user.fields",
            )
        )
    if media:
        out.append(
            P(
                "media_fields",
                "string",
                desc="Comma separated media.fields to return.",
                default=_DEFAULT_MEDIA_FIELDS if defaults else None,
                api_name="media.fields",
            )
        )
    if expansions:
        out.append(
            P(
                "expansions",
                "string",
                desc="Comma separated expansions to resolve.",
                default=_DEFAULT_EXPANSIONS if defaults else None,
            )
        )
    return tuple(out)


ME = P("me", "string", desc="Ignored - resolved to the authenticated account id.")

TOOLS: list[Tool] = []


def add(*tools: Tool) -> None:
    TOOLS.extend(tools)


# --------------------------------------------------------------------------
# Posts
# --------------------------------------------------------------------------
add(
    T(
        "post_tweet",
        "POST",
        "/2/tweets",
        "Post a new tweet, optionally replying to a tweet, quoting a tweet or attaching uploaded media.",
        family="Posts",
        params=(
            P("text", "string", required=True, desc="Tweet text (280 characters, 28000 for long posts)."),
            P("in_reply_to_tweet_id", "string", desc="Tweet id this post replies to."),
            P("quote_tweet_id", "string", desc="Tweet id this post quotes."),
            P("media_ids", "array", desc="Media ids returned by upload_media to attach."),
            P("for_super_followers_only", "boolean", desc="Restrict the post to super followers."),
        ),
        body=("text", "reply", "quote_tweet_id", "media", "for_super_followers_only"),
        output="tweet",
        scopes=("tweet.write", "users.read"),
    ),
    T(
        "reply_to_tweet",
        "POST",
        "/2/tweets",
        "Reply to an existing tweet.",
        family="Posts",
        params=(
            P("tweet_id", "string", required=True, desc="Tweet being replied to."),
            P("text", "string", required=True, desc="Reply text."),
            P("media_ids", "array", desc="Media ids returned by upload_media to attach."),
        ),
        body=("text", "reply", "media"),
        output="tweet",
        scopes=("tweet.write", "users.read"),
    ),
    T(
        "delete_tweet",
        "DELETE",
        "/2/tweets/{tweet_id}",
        "Delete a tweet owned by the authenticated account.",
        family="Posts",
        params=(P("tweet_id", "string", required=True, desc="Tweet id to delete."),),
        output="success",
        scopes=("tweet.write", "users.read"),
    ),
    T(
        "get_tweet",
        "GET",
        "/2/tweets/{tweet_id}",
        "Get a single tweet with optional expansions and field sets.",
        family="Posts",
        params=(P("tweet_id", "string", required=True, desc="Tweet id."),) + fields(defaults=True),
        output="tweet",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_posts_by_ids",
        "GET",
        "/2/tweets",
        "Get several tweets by id.",
        family="Posts",
        params=(P("ids", "array", required=True, desc="Tweet ids (max 100)."),) + fields(),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "search_tweets",
        "GET",
        "/2/tweets/search/recent",
        "Search the last 7 days of tweets.",
        family="Posts",
        params=(
            P("query", "string", required=True, desc="Search query, e.g. 'AI lang:en -is:retweet'."),
        )
        + paging(10, 100)
        + fields(defaults=True),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "search_all_tweets",
        "GET",
        "/2/tweets/search/all",
        "Search the full tweet archive (requires full archive access).",
        family="Posts",
        params=(
            P("query", "string", required=True, desc="Search query."),
        )
        + paging(10, 100)
        + fields(defaults=True),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_recent_post_counts",
        "GET",
        "/2/tweets/counts/recent",
        "Count tweets matching a query over the last 7 days.",
        family="Posts",
        params=(
            P("query", "string", required=True, desc="Search query."),
            P("granularity", "string", desc="minute, hour or day.", enum=("minute", "hour", "day")),
            P("start_time", "string", desc="ISO 8601 start time."),
            P("end_time", "string", desc="ISO 8601 end time."),
            P("since_id", "string", desc="Return results newer than this id."),
            P("until_id", "string", desc="Return results older than this id."),
            P("next_token", "string", desc="Token from a previous counts call."),
        ),
        output="counts",
        scopes=("tweet.read",),
    ),
    T(
        "get_all_post_counts",
        "GET",
        "/2/tweets/counts/all",
        "Count tweets matching a query across the full archive.",
        family="Posts",
        params=(
            P("query", "string", required=True, desc="Search query."),
            P("granularity", "string", desc="minute, hour or day.", enum=("minute", "hour", "day")),
            P("start_time", "string", desc="ISO 8601 start time."),
            P("end_time", "string", desc="ISO 8601 end time."),
            P("since_id", "string", desc="Return results newer than this id."),
            P("until_id", "string", desc="Return results older than this id."),
            P("next_token", "string", desc="Token from a previous counts call."),
        ),
        output="counts",
        scopes=("tweet.read",),
    ),
    T(
        "get_quote_tweets",
        "GET",
        "/2/tweets/{tweet_id}/quote_tweets",
        "List the tweets quoting a given tweet.",
        family="Posts",
        params=(P("tweet_id", "string", required=True, desc="Tweet id."),) + paging(10, 100) + fields(),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_retweeted_by",
        "GET",
        "/2/tweets/{tweet_id}/retweeted_by",
        "List the users who reposted a given tweet.",
        family="Posts",
        params=(P("tweet_id", "string", required=True, desc="Tweet id."),) + paging(10, 100) + fields(),
        output="user_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_liking_users",
        "GET",
        "/2/tweets/{tweet_id}/liking_users",
        "List the users who liked a given tweet.",
        family="Posts",
        params=(P("tweet_id", "string", required=True, desc="Tweet id."),) + paging(10, 100) + fields(),
        output="user_list",
        scopes=("like.read", "tweet.read", "users.read"),
    ),
    T(
        "get_post_reposts",
        "GET",
        "/2/tweets/{tweet_id}/retweets",
        "List the reposts of a given tweet.",
        family="Posts",
        params=(P("tweet_id", "string", required=True, desc="Tweet id."),) + paging(10, 100) + fields(),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "hide_reply",
        "PUT",
        "/2/tweets/{tweet_id}/hidden",
        "Hide or unhide a reply to one of your tweets.",
        family="Posts",
        params=(
            P("tweet_id", "string", required=True, desc="Reply tweet id."),
            P("hidden", "boolean", required=True, desc="True hides the reply, false unhides it."),
        ),
        body=("hidden",),
        output="success",
        scopes=("tweet.moderate.write", "tweet.read", "users.read"),
    ),
    T(
        "get_post_analytics",
        "GET",
        "/2/tweets/analytics",
        "Post engagement analytics (Enterprise only).",
        family="Posts",
        params=(
            P("ids", "array", required=True, desc="Tweet ids."),
            P("start_time", "string", desc="ISO 8601 start time."),
            P("end_time", "string", desc="ISO 8601 end time."),
            P("granularity", "string", desc="day or hourly.", enum=("day", "hourly")),
        ),
        output="json",
        scopes=("tweet.read", "users.read"),
    ),
)

# --------------------------------------------------------------------------
# Likes and reposts
# --------------------------------------------------------------------------
add(
    T(
        "like_tweet",
        "POST",
        "/2/users/{me}/likes",
        "Like a tweet.",
        family="Likes",
        params=(
            P("tweet_id", "string", required=True, desc="Tweet id to like."),
        ),
        body=("tweet_id",),
        output="success",
        scopes=("like.write", "tweet.read", "users.read"),
    ),
    T(
        "unlike_tweet",
        "DELETE",
        "/2/users/{me}/likes/{tweet_id}",
        "Remove a like from a tweet.",
        family="Likes",
        params=(
            P("tweet_id", "string", required=True, desc="Tweet id to unlike."),
        ),
        output="success",
        scopes=("like.write", "tweet.read", "users.read"),
    ),
    T(
        "get_liked_tweets",
        "GET",
        "/2/users/{user_id}/liked_tweets",
        "List the tweets liked by a user.",
        family="Likes",
        params=(P("user_id", "string", required=True, desc="User id."),) + paging(10, 100) + fields(),
        output="tweet_list",
        scopes=("like.read", "tweet.read", "users.read"),
    ),
    T(
        "retweet",
        "POST",
        "/2/users/{me}/retweets",
        "Repost (retweet) a tweet.",
        family="Likes",
        params=(
            P("tweet_id", "string", required=True, desc="Tweet id to repost."),
        ),
        body=("tweet_id",),
        output="success",
        scopes=("tweet.read", "tweet.write", "users.read"),
    ),
    T(
        "unrepost",
        "DELETE",
        "/2/users/{me}/retweets/{source_tweet_id}",
        "Undo a repost.",
        family="Likes",
        params=(
            P("source_tweet_id", "string", required=True, desc="Id of the reposted tweet."),
        ),
        output="success",
        scopes=("tweet.read", "tweet.write", "users.read"),
    ),
    T(
        "get_user_reposts",
        "GET",
        "/2/users/{user_id}/retweets",
        "List the reposts made by a user.",
        family="Likes",
        params=(P("user_id", "string", required=True, desc="User id."),) + paging(10, 100) + fields(),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
)

# --------------------------------------------------------------------------
# Users, follows, bookmarks, blocks, mutes
# --------------------------------------------------------------------------
add(
    T(
        "get_me",
        "GET",
        "/2/users/me",
        "Get the authenticated account (id, username, name).",
        family="Users",
        params=(
            P("user_fields", "string", desc="Comma separated user.fields.", default="id,username,name,created_at", api_name="user.fields"),
        ),
        output="user",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_user",
        "GET",
        "/2/users/by/username/{username}",
        "Get a user profile by username (without the @).",
        family="Users",
        params=(
            P("username", "string", required=True, desc="Username without @."),
            P(
                "user_fields",
                "string",
                desc="Comma separated user.fields.",
                default="created_at,description,public_metrics,profile_image_url,verified,url",
                api_name="user.fields",
            ),
        ),
        output="user",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_user_by_id",
        "GET",
        "/2/users/{user_id}",
        "Get a user profile by id.",
        family="Users",
        params=(
            P("user_id", "string", required=True, desc="User id."),
            P("user_fields", "string", desc="Comma separated user.fields.", api_name="user.fields"),
        ),
        output="user",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_users_by_ids",
        "GET",
        "/2/users",
        "Get several users by id.",
        family="Users",
        params=(
            P("ids", "array", required=True, desc="User ids (max 100)."),
            P("user_fields", "string", desc="Comma separated user.fields.", api_name="user.fields"),
        ),
        output="user_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_users_by_usernames",
        "GET",
        "/2/users/by",
        "Get several users by username.",
        family="Users",
        params=(
            P("usernames", "array", required=True, desc="Usernames without @ (max 100)."),
            P("user_fields", "string", desc="Comma separated user.fields.", api_name="user.fields"),
        ),
        output="user_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "search_users",
        "GET",
        "/2/users/search",
        "Search users by keyword.",
        family="Users",
        params=(
            P("query", "string", required=True, desc="Search query."),
        )
        + paging(10, 100)
        + fields(user=True, media=False, tweet=False),
        output="user_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_user_tweets",
        "GET",
        "/2/users/{user_id}/tweets",
        "Get the recent tweets of a user.",
        family="Users",
        params=(
            P("username", "string", desc="Username without @ (resolved to a user id)."),
            P("user_id", "string", desc="User id (use instead of username)."),
            P("exclude", "array", desc="Exclude retweets, replies or both."),
            P("exclude_replies", "boolean", desc="Exclude replies."),
            P("exclude_retweets", "boolean", desc="Exclude retweets."),
        )
        + paging(10, 100)
        + fields(),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_user_mentions",
        "GET",
        "/2/users/{user_id}/mentions",
        "Get tweets mentioning a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id."),) + paging(10, 100) + fields(),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_user_timeline",
        "GET",
        "/2/users/{user_id}/timelines/reverse_chronological",
        "Get the reverse chronological home timeline of a user.",
        family="Users",
        params=(
            P("user_id", "string", required=True, desc="User id."),
            P("since_id", "string", desc="Return results newer than this id."),
            P("until_id", "string", desc="Return results older than this id."),
            P("start_time", "string", desc="ISO 8601 start time."),
            P("end_time", "string", desc="ISO 8601 end time."),
        )
        + paging(10, 100)
        + fields(),
        output="tweet_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_reposts_of_me",
        "GET",
        "/2/users/reposts_of_me",
        "Get reposts of the authenticated account.",
        family="Users",
        params=(
            P("since_id", "string", desc="Return results newer than this id."),
            P("until_id", "string", desc="Return results older than this id."),
        )
        + paging(10, 100)
        + fields(),
        output="tweet_list",
        scopes=("timeline.read", "tweet.read"),
    ),
    T(
        "get_user_affiliates",
        "GET",
        "/2/users/{user_id}/affiliates",
        "Get the affiliates of a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id."),) + paging(10, 100),
        output="user_list",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "follow_user",
        "POST",
        "/2/users/{me}/following",
        "Follow a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id to follow."),),
        body=("target_user_id",),
        output="success",
        scopes=("follows.write", "tweet.read", "users.read"),
    ),
    T(
        "unfollow_user",
        "DELETE",
        "/2/users/{me}/following/{user_id}",
        "Unfollow a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id to unfollow."),),
        output="success",
        scopes=("follows.write", "tweet.read", "users.read"),
    ),
    T(
        "get_following",
        "GET",
        "/2/users/{me}/following",
        "List the accounts the authenticated account follows.",
        family="Users",
        params=paging(100, 1000)
        + (
            P("user_fields", "string", desc="Comma separated user.fields.", api_name="user.fields"),
        ),
        output="user_list",
        scopes=("follows.read", "tweet.read", "users.read"),
    ),
    T(
        "get_followers",
        "GET",
        "/2/users/{me}/followers",
        "List the accounts following the authenticated account.",
        family="Users",
        params=paging(100, 1000)
        + (
            P("user_fields", "string", desc="Comma separated user.fields.", api_name="user.fields"),
        ),
        output="user_list",
        scopes=("follows.read", "tweet.read", "users.read"),
    ),
    T(
        "get_user_following",
        "GET",
        "/2/users/{user_id}/following",
        "List the accounts a specific user follows.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id."),) + paging(100, 1000),
        output="user_list",
        scopes=("follows.read", "tweet.read", "users.read"),
    ),
    T(
        "get_user_followers",
        "GET",
        "/2/users/{user_id}/followers",
        "List the followers of a specific user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id."),) + paging(100, 1000),
        output="user_list",
        scopes=("follows.read", "tweet.read", "users.read"),
    ),
    T(
        "block_user",
        "POST",
        "/2/users/{me}/blocking",
        "Block a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id to block."),),
        body=("target_user_id",),
        output="success",
        scopes=("block.write", "tweet.read", "users.read"),
    ),
    T(
        "unblock_user",
        "DELETE",
        "/2/users/{me}/blocking/{user_id}",
        "Unblock a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id to unblock."),),
        output="success",
        scopes=("block.write", "tweet.read", "users.read"),
    ),
    T(
        "get_blocked_users",
        "GET",
        "/2/users/{me}/blocking",
        "List the accounts blocked by the authenticated account.",
        family="Users",
        params=paging(100, 1000),
        output="user_list",
        scopes=("block.read", "tweet.read", "users.read"),
    ),
    T(
        "mute_user",
        "POST",
        "/2/users/{me}/muting",
        "Mute a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id to mute."),),
        body=("target_user_id",),
        output="success",
        scopes=("mute.write", "tweet.read", "users.read"),
    ),
    T(
        "unmute_user",
        "DELETE",
        "/2/users/{me}/muting/{user_id}",
        "Unmute a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id to unmute."),),
        output="success",
        scopes=("mute.write", "tweet.read", "users.read"),
    ),
    T(
        "get_muting_users",
        "GET",
        "/2/users/{me}/muting",
        "List the accounts muted by the authenticated account.",
        family="Users",
        params=paging(100, 1000),
        output="user_list",
        scopes=("mute.read", "tweet.read", "users.read"),
    ),
    T(
        "block_dms",
        "POST",
        "/2/users/{me}/dm/block",
        "Block direct messages from a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id."),),
        body=("target_user_id",),
        output="success",
        scopes=("dm.write", "tweet.read", "users.read"),
    ),
    T(
        "unblock_dms",
        "POST",
        "/2/users/{me}/dm/unblock",
        "Unblock direct messages from a user.",
        family="Users",
        params=(P("user_id", "string", required=True, desc="User id."),),
        body=("target_user_id",),
        output="success",
        scopes=("dm.write", "tweet.read", "users.read"),
    ),
    T(
        "get_bookmarks",
        "GET",
        "/2/users/{me}/bookmarks",
        "List the bookmarks of the authenticated account.",
        family="Bookmarks",
        params=paging(10, 100) + fields(),
        output="tweet_list",
        scopes=("bookmark.read", "tweet.read", "users.read"),
    ),
    T(
        "create_bookmark",
        "POST",
        "/2/users/{me}/bookmarks",
        "Bookmark a tweet.",
        family="Bookmarks",
        params=(P("tweet_id", "string", required=True, desc="Tweet id to bookmark."),),
        body=("tweet_id",),
        output="success",
        scopes=("bookmark.write", "tweet.read", "users.read"),
    ),
    T(
        "delete_bookmark",
        "DELETE",
        "/2/users/{me}/bookmarks/{tweet_id}",
        "Remove a bookmark.",
        family="Bookmarks",
        params=(P("tweet_id", "string", required=True, desc="Bookmarked tweet id."),),
        output="success",
        scopes=("bookmark.write", "tweet.read", "users.read"),
    ),
    T(
        "get_bookmark_folders",
        "GET",
        "/2/users/{me}/bookmarks/folders",
        "List the bookmark folders of the authenticated account.",
        family="Bookmarks",
        params=paging(10, 100),
        output="json",
        scopes=("bookmark.read", "users.read"),
    ),
    T(
        "create_bookmark_folder",
        "POST",
        "/2/users/{me}/bookmarks/folders",
        "Create a bookmark folder.",
        family="Bookmarks",
        params=(P("name", "string", required=True, desc="Folder name."),),
        body=("name",),
        output="json",
        scopes=("bookmark.write", "users.read"),
    ),
    T(
        "get_bookmarks_by_folder",
        "GET",
        "/2/users/{me}/bookmarks/folders/{folder_id}",
        "List the bookmarks inside a folder.",
        family="Bookmarks",
        params=(
            P("folder_id", "string", required=True, desc="Bookmark folder id."),
        )
        + paging(10, 100)
        + fields(),
        output="tweet_list",
        scopes=("bookmark.read", "tweet.read", "users.read"),
    ),
)

# --------------------------------------------------------------------------
# Lists
# --------------------------------------------------------------------------
add(
    T(
        "create_list",
        "POST",
        "/2/lists",
        "Create a list.",
        family="Lists",
        params=(
            P("name", "string", required=True, desc="List name."),
            P("description", "string", desc="List description."),
            P("private", "boolean", desc="Whether the list is private."),
        ),
        body=("name", "description", "private"),
        output="json",
        scopes=("list.read", "list.write", "tweet.read", "users.read"),
    ),
    T(
        "get_list",
        "GET",
        "/2/lists/{list_id}",
        "Get a list by id.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),),
        output="json",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
    T(
        "update_list",
        "PUT",
        "/2/lists/{list_id}",
        "Update a list name, description or privacy.",
        family="Lists",
        params=(
            P("list_id", "string", required=True, desc="List id."),
            P("name", "string", desc="New list name."),
            P("description", "string", desc="New description."),
            P("private", "boolean", desc="New privacy flag."),
        ),
        body=("name", "description", "private"),
        output="json",
        scopes=("list.write", "tweet.read", "users.read"),
    ),
    T(
        "delete_list",
        "DELETE",
        "/2/lists/{list_id}",
        "Delete a list.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),),
        output="success",
        scopes=("list.write", "tweet.read", "users.read"),
    ),
    T(
        "get_list_members",
        "GET",
        "/2/lists/{list_id}/members",
        "List the members of a list.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),) + paging(10, 100),
        output="user_list",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
    T(
        "add_list_member",
        "POST",
        "/2/lists/{list_id}/members",
        "Add a member to a list.",
        family="Lists",
        params=(
            P("list_id", "string", required=True, desc="List id."),
            P("user_id", "string", required=True, desc="User id to add."),
        ),
        body=("user_id",),
        output="success",
        scopes=("list.write", "tweet.read", "users.read"),
    ),
    T(
        "remove_list_member",
        "DELETE",
        "/2/lists/{list_id}/members/{user_id}",
        "Remove a member from a list.",
        family="Lists",
        params=(
            P("list_id", "string", required=True, desc="List id."),
            P("user_id", "string", required=True, desc="User id to remove."),
        ),
        output="success",
        scopes=("list.write", "tweet.read", "users.read"),
    ),
    T(
        "get_list_tweets",
        "GET",
        "/2/lists/{list_id}/tweets",
        "List the tweets of a list.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),) + paging(10, 100) + fields(),
        output="tweet_list",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
    T(
        "get_list_followers",
        "GET",
        "/2/lists/{list_id}/followers",
        "List the followers of a list.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),) + paging(10, 100),
        output="user_list",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
    T(
        "get_owned_lists",
        "GET",
        "/2/users/{me}/owned_lists",
        "List the lists owned by the authenticated account.",
        family="Lists",
        params=paging(10, 100),
        output="json",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
    T(
        "get_followed_lists",
        "GET",
        "/2/users/{me}/followed_lists",
        "List the lists followed by the authenticated account.",
        family="Lists",
        params=paging(10, 100),
        output="json",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
    T(
        "follow_list",
        "POST",
        "/2/users/{me}/followed_lists",
        "Follow a list.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),),
        body=("list_id",),
        output="success",
        scopes=("list.write", "tweet.read", "users.read"),
    ),
    T(
        "unfollow_list",
        "DELETE",
        "/2/users/{me}/followed_lists/{list_id}",
        "Unfollow a list.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),),
        output="success",
        scopes=("list.write", "tweet.read", "users.read"),
    ),
    T(
        "get_pinned_lists",
        "GET",
        "/2/users/{me}/pinned_lists",
        "List the pinned lists of the authenticated account.",
        family="Lists",
        params=paging(10, 100),
        output="json",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
    T(
        "pin_list",
        "POST",
        "/2/users/{me}/pinned_lists",
        "Pin a list.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),),
        body=("list_id",),
        output="success",
        scopes=("list.write", "tweet.read", "users.read"),
    ),
    T(
        "unpin_list",
        "DELETE",
        "/2/users/{me}/pinned_lists/{list_id}",
        "Unpin a list.",
        family="Lists",
        params=(P("list_id", "string", required=True, desc="List id."),),
        output="success",
        scopes=("list.write", "tweet.read", "users.read"),
    ),
    T(
        "get_list_memberships",
        "GET",
        "/2/users/{me}/list_memberships",
        "List the lists the authenticated account is a member of.",
        family="Lists",
        params=paging(10, 100),
        output="json",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
)

# --------------------------------------------------------------------------
# Media
# --------------------------------------------------------------------------
add(
    T(
        "upload_media",
        "POST",
        "/2/media/upload",
        "Upload media (image, video or GIF) and return the media id for use in post_tweet.",
        family="Media",
        auth="oauth2",
        params=(
            P("media_base64", "string", required=True, desc="Base64 encoded file content."),
            P("media_category", "string", desc="Media category.", default="tweet_image"),
            P("media_type", "string", desc="MIME type of the file.", default="image/png"),
            P("filename", "string", desc="File name used in the multipart body.", default="upload.png"),
            P("additional_owners", "array", desc="User ids allowed to use the media."),
        ),
        output="media",
        scopes=("media.write",),
    ),
    T(
        "get_media_upload_status",
        "GET",
        "/2/media/upload",
        "Check the status of an asynchronous media upload.",
        family="Media",
        auth="oauth2",
        params=(
            P("command", "string", required=True, desc="Upload command, e.g. STATUS.", enum=("STATUS",)),
            P("media_id", "string", required=True, desc="Media id returned by upload_media."),
        ),
        output="json",
        scopes=("media.write",),
    ),
    T(
        "create_media_metadata",
        "POST",
        "/2/media/metadata",
        "Attach alt text or metadata to uploaded media.",
        family="Media",
        auth="oauth2",
        params=(
            P("media_id", "string", required=True, desc="Media id."),
            P("media_category", "string", desc="Media category.", default="tweet_image"),
            P("alt_text", "string", desc="Alternative text for the media."),
        ),
        body=("media_id", "media_category", "alt_text"),
        output="success",
        scopes=("media.write",),
    ),
    T(
        "create_media_subtitles",
        "POST",
        "/2/media/subtitles",
        "Add subtitles to a video.",
        family="Media",
        auth="oauth2",
        params=(
            P("media_id", "string", required=True, desc="Media id."),
            P("language_code", "string", required=True, desc="BCP 47 language code, e.g. en."),
            P("name", "string", desc="Subtitle name."),
            P("subtitles_base64", "string", desc="Base64 encoded SRT/VTT content."),
        ),
        body=("media_id", "language_code", "name", "subtitles"),
        output="success",
        scopes=("media.write",),
    ),
    T(
        "delete_media_subtitles",
        "DELETE",
        "/2/media/subtitles",
        "Delete the subtitles of a video.",
        family="Media",
        auth="oauth2",
        params=(
            P("media_id", "string", required=True, desc="Media id."),
            P("language_code", "string", required=True, desc="BCP 47 language code."),
        ),
        body=("media_id", "language_code"),
        output="success",
        scopes=("media.write",),
    ),
    T(
        "get_media_by_key",
        "GET",
        "/2/media/{media_key}",
        "Get media metadata by media key.",
        family="Media",
        params=(
            P("media_key", "string", required=True, desc="Media key."),
            P("media_fields", "string", desc="Comma separated media.fields.", api_name="media.fields"),
        ),
        output="json",
        scopes=("tweet.read",),
    ),
    T(
        "get_media_by_keys",
        "GET",
        "/2/media",
        "Get metadata for several media keys.",
        family="Media",
        params=(
            P("media_keys", "array", required=True, desc="Media keys."),
            P("media_category", "string", desc="Media category.", default="tweet_image"),
            P("media_fields", "string", desc="Comma separated media.fields.", api_name="media.fields"),
        ),
        output="json",
        scopes=("tweet.read",),
    ),
)

# --------------------------------------------------------------------------
# Trends, Spaces
# --------------------------------------------------------------------------
add(
    T(
        "get_trends_by_woeid",
        "GET",
        "/2/trends/by/woeid/{woeid}",
        "Get trending topics for a location (WOEID).",
        family="Trends",
        params=(P("woeid", "string", required=True, desc="Where On Earth id, e.g. 23424977 for the US."),),
        output="json",
        scopes=(),
    ),
    T(
        "get_personalized_trends",
        "GET",
        "/2/users/personalized_trends",
        "Get trends personalized for the authenticated account.",
        family="Trends",
        params=(
            P("max_categories", "integer", desc="Maximum number of trend categories.", default=20, minimum=1, maximum=50),
            P("trend_granularity", "string", desc="Trend granularity.", enum=("hour", "day")),
        ),
        output="json",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "search_spaces",
        "GET",
        "/2/spaces/search",
        "Search live Spaces.",
        family="Spaces",
        auth="oauth2",
        params=(
            P("query", "string", required=True, desc="Search query."),
        )
        + paging(10, 100)
        + (
            P("space_fields", "string", desc="Comma separated space.fields.", api_name="space.fields"),
            P("topic_fields", "string", desc="Comma separated topic.fields.", api_name="topic.fields"),
            P("speaker_fields", "string", desc="Comma separated speaker.fields.", api_name="speaker.fields"),
        ),
        output="json",
        scopes=("space.read", "tweet.read", "users.read"),
    ),
    T(
        "get_space",
        "GET",
        "/2/spaces/{space_id}",
        "Get a Space by id.",
        family="Spaces",
        auth="oauth2",
        params=(
            P("space_id", "string", required=True, desc="Space id."),
            P("space_fields", "string", desc="Comma separated space.fields.", api_name="space.fields"),
            P("topic_fields", "string", desc="Comma separated topic.fields.", api_name="topic.fields"),
            P("speaker_fields", "string", desc="Comma separated speaker.fields.", api_name="speaker.fields"),
        ),
        output="json",
        scopes=("space.read", "tweet.read", "users.read"),
    ),
    T(
        "get_spaces_by_ids",
        "GET",
        "/2/spaces",
        "Get several Spaces by id.",
        family="Spaces",
        auth="oauth2",
        params=(
            P("ids", "array", required=True, desc="Space ids."),
            P("space_fields", "string", desc="Comma separated space.fields.", api_name="space.fields"),
        ),
        output="json",
        scopes=("space.read", "tweet.read", "users.read"),
    ),
    T(
        "get_spaces_by_creator_ids",
        "GET",
        "/2/spaces/by/creator_ids",
        "Get the Spaces created by given users.",
        family="Spaces",
        auth="oauth2",
        params=(
            P("user_ids", "array", required=True, desc="Creator user ids."),
            P("space_fields", "string", desc="Comma separated space.fields.", api_name="space.fields"),
        ),
        output="json",
        scopes=("space.read", "tweet.read", "users.read"),
    ),
    T(
        "get_space_tweets",
        "GET",
        "/2/spaces/{space_id}/tweets",
        "Get the tweets of a Space.",
        family="Spaces",
        auth="oauth2",
        params=(
            P("space_id", "string", required=True, desc="Space id."),
        )
        + paging(10, 100)
        + fields(),
        output="tweet_list",
        scopes=("space.read", "tweet.read", "users.read"),
    ),
    T(
        "get_space_buyers",
        "GET",
        "/2/spaces/{space_id}/buyers",
        "Get the ticket buyers of a ticketed Space.",
        family="Spaces",
        auth="oauth2",
        params=(P("space_id", "string", required=True, desc="Space id."),) + paging(10, 100),
        output="user_list",
        scopes=("space.read", "tweet.read", "users.read"),
    ),
)

# --------------------------------------------------------------------------
# Direct messages and Chat
# --------------------------------------------------------------------------
add(
    T(
        "get_dm_events",
        "GET",
        "/2/dm_events",
        "List direct message events for the authenticated account.",
        family="Direct Messages",
        auth="oauth2",
        params=(
            P("max_results", "integer", desc="Number of events.", default=100, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
            P("since", "string", desc="Return events created after this id."),
            P("until", "string", desc="Return events created before this id."),
            P("event_types", "array", desc="Filter by event type, e.g. MessageCreate."),
        ),
        output="json",
        scopes=("dm.read", "tweet.read", "users.read"),
    ),
    T(
        "get_dm_event",
        "GET",
        "/2/dm_events/{event_id}",
        "Get a single direct message event.",
        family="Direct Messages",
        auth="oauth2",
        params=(P("event_id", "string", required=True, desc="DM event id."),),
        output="json",
        scopes=("dm.read", "tweet.read", "users.read"),
    ),
    T(
        "delete_dm_event",
        "DELETE",
        "/2/dm_events/{event_id}",
        "Delete a direct message event.",
        family="Direct Messages",
        auth="oauth2",
        params=(P("event_id", "string", required=True, desc="DM event id."),),
        output="success",
        scopes=("dm.read", "dm.write"),
    ),
    T(
        "get_dm_events_by_participant",
        "GET",
        "/2/dm_conversations/with/{participant_id}/dm_events",
        "List DM events exchanged with a participant.",
        family="Direct Messages",
        auth="oauth2",
        params=(
            P("participant_id", "string", required=True, desc="Participant user id."),
            P("max_results", "integer", desc="Number of events.", default=100, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
        ),
        output="json",
        scopes=("dm.read", "tweet.read", "users.read"),
    ),
    T(
        "get_dm_events_by_conversation",
        "GET",
        "/2/dm_conversations/{dm_conversation_id}/dm_events",
        "List the DM events of a conversation.",
        family="Direct Messages",
        auth="oauth2",
        params=(
            P("dm_conversation_id", "string", required=True, desc="Conversation id."),
            P("max_results", "integer", desc="Number of events.", default=100, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
        ),
        output="json",
        scopes=("dm.read", "tweet.read", "users.read"),
    ),
    T(
        "create_dm_conversation",
        "POST",
        "/2/dm_conversations",
        "Create a direct message conversation.",
        family="Direct Messages",
        auth="oauth2",
        params=(
            P("participant_ids", "array", required=True, desc="Participant user ids."),
            P("text", "string", desc="Message text."),
            P("media_ids", "array", desc="Media ids to attach."),
        ),
        body=("participant_ids", "media", "text"),
        output="json",
        scopes=("dm.write", "tweet.read", "users.read"),
    ),
    T(
        "send_dm_by_participant",
        "POST",
        "/2/dm_conversations/with/{participant_id}/messages",
        "Send a direct message to a participant.",
        family="Direct Messages",
        auth="oauth2",
        params=(
            P("participant_id", "string", required=True, desc="Participant user id."),
            P("text", "string", desc="Message text."),
            P("media_ids", "array", desc="Media ids to attach."),
        ),
        body=("text", "media"),
        output="json",
        scopes=("dm.write", "tweet.read", "users.read"),
    ),
    T(
        "send_dm_by_conversation",
        "POST",
        "/2/dm_conversations/{dm_conversation_id}/messages",
        "Send a direct message inside an existing conversation.",
        family="Direct Messages",
        auth="oauth2",
        params=(
            P("dm_conversation_id", "string", required=True, desc="Conversation id."),
            P("text", "string", desc="Message text."),
            P("media_ids", "array", desc="Media ids to attach."),
        ),
        body=("text", "media"),
        output="json",
        scopes=("dm.write", "tweet.read", "users.read"),
    ),
    T(
        "get_chat_conversations",
        "GET",
        "/2/chat/conversations",
        "List chat (group DM) conversations.",
        family="Chat",
        auth="oauth2",
        params=(
            P("max_results", "integer", desc="Number of conversations.", default=100, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
        ),
        output="json",
        scopes=("dm.read", "tweet.read", "users.read"),
    ),
    T(
        "get_chat_conversation",
        "GET",
        "/2/chat/conversations/{conversation_id}",
        "Get a chat conversation.",
        family="Chat",
        auth="oauth2",
        params=(P("conversation_id", "string", required=True, desc="Conversation id."),),
        output="json",
        scopes=("dm.read", "tweet.read", "users.read"),
    ),
    T(
        "send_chat_message",
        "POST",
        "/2/chat/conversations/{conversation_id}/messages",
        "Send a message in a chat conversation.",
        family="Chat",
        auth="oauth2",
        params=(
            P("conversation_id", "string", required=True, desc="Conversation id."),
            P("text", "string", desc="Message text."),
        ),
        body=("text",),
        output="json",
        scopes=("dm.write", "tweet.read", "users.read"),
    ),
    T(
        "archive_chat_conversation",
        "POST",
        "/2/chat/conversations/{conversation_id}/archive",
        "Archive a chat conversation.",
        family="Chat",
        auth="oauth2",
        params=(P("conversation_id", "string", required=True, desc="Conversation id."),),
        output="success",
        scopes=("dm.write", "tweet.read", "users.read"),
    ),
    T(
        "unarchive_chat_conversation",
        "DELETE",
        "/2/chat/conversations/{conversation_id}/archive",
        "Unarchive a chat conversation.",
        family="Chat",
        auth="oauth2",
        params=(P("conversation_id", "string", required=True, desc="Conversation id."),),
        output="success",
        scopes=("dm.write", "tweet.read", "users.read"),
    ),
)

# --------------------------------------------------------------------------
# Communities, Community Notes, News
# --------------------------------------------------------------------------
add(
    T(
        "get_community",
        "GET",
        "/2/communities/{community_id}",
        "Get a community by id.",
        family="Communities",
        params=(P("community_id", "string", required=True, desc="Community id."),),
        output="json",
        scopes=("list.read", "tweet.read", "users.read"),
    ),
    T(
        "search_communities",
        "GET",
        "/2/communities/search",
        "Search communities by name.",
        family="Communities",
        params=(
            P("query", "string", required=True, desc="Search query."),
        )
        + paging(10, 100),
        output="json",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "create_community_note",
        "POST",
        "/2/notes",
        "Create a Community Note.",
        family="Community Notes",
        params=(
            P("text", "string", required=True, desc="Note text."),
            P("media_id", "string", desc="Media id proving the note."),
            P("test_tweet_id", "string", desc="Tweet used for testing the note."),
        ),
        body=("text", "media_id", "test_tweet_id"),
        output="json",
        scopes=("tweet.write",),
    ),
    T(
        "evaluate_community_note",
        "POST",
        "/2/notes/evaluate",
        "Evaluate whether a Community Note is helpful.",
        family="Community Notes",
        params=(P("community_note_id", "string", required=True, desc="Community note id."),),
        body=("community_note_id",),
        output="json",
        scopes=("tweet.write",),
    ),
    T(
        "delete_community_note",
        "DELETE",
        "/2/notes/{note_id}",
        "Delete a Community Note.",
        family="Community Notes",
        params=(P("note_id", "string", required=True, desc="Community note id."),),
        output="success",
        scopes=("tweet.write",),
    ),
    T(
        "search_notes_written",
        "GET",
        "/2/notes/search/notes_written",
        "Search Community Notes written by a user.",
        family="Community Notes",
        params=(
            P("user_id", "string", desc="User id."),
            P("max_results", "integer", desc="Number of notes.", default=10, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
        ),
        output="json",
        scopes=("tweet.read",),
    ),
    T(
        "search_posts_eligible_for_notes",
        "GET",
        "/2/notes/search/posts_eligible_for_notes",
        "Search posts that are eligible for a Community Note.",
        family="Community Notes",
        params=(
            P("query", "string", desc="Search query."),
            P("max_results", "integer", desc="Number of posts.", default=10, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
        ),
        output="json",
        scopes=("tweet.read",),
    ),
    T(
        "search_news",
        "GET",
        "/2/news/search",
        "Search news stories attached to posts.",
        family="News",
        params=(
            P("query", "string", required=True, desc="Search query."),
            P("max_results", "integer", desc="Number of stories.", default=10, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
        ),
        output="json",
        scopes=("tweet.read", "users.read"),
    ),
    T(
        "get_news",
        "GET",
        "/2/news/{news_id}",
        "Get a news story by id.",
        family="News",
        params=(P("news_id", "string", required=True, desc="News story id."),),
        output="json",
        scopes=("tweet.read", "users.read"),
    ),
)

# --------------------------------------------------------------------------
# Compliance, account, usage
# --------------------------------------------------------------------------
add(
    T(
        "create_compliance_job",
        "POST",
        "/2/compliance/jobs",
        "Create a compliance job to delete posts or accounts by id.",
        family="Compliance",
        params=(
            P("type", "string", required=True, desc="Job type.", enum=("tweets", "accounts")),
            P("ids", "array", desc="Post or account ids to remove."),
            P("resumable", "boolean", desc="Whether the job can be resumed."),
            P("name", "string", desc="Job name."),
        ),
        body=("type", "ids", "resumable", "name"),
        output="json",
        scopes=(),
    ),
    T(
        "list_compliance_jobs",
        "GET",
        "/2/compliance/jobs",
        "List compliance jobs.",
        family="Compliance",
        params=(
            P("type", "string", desc="Filter by job type.", enum=("tweets", "accounts")),
            P("status", "string", desc="Filter by job status."),
            P("max_results", "integer", desc="Number of jobs.", default=100, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
        ),
        output="json",
        scopes=(),
    ),
    T(
        "get_compliance_job",
        "GET",
        "/2/compliance/jobs/{job_id}",
        "Get a compliance job by id.",
        family="Compliance",
        params=(P("job_id", "string", required=True, desc="Compliance job id."),),
        output="json",
        scopes=(),
    ),
    T(
        "download_compliance_results",
        "GET",
        "/2/compliance/jobs/{job_id}/download",
        "Download the results of a compliance job.",
        family="Compliance",
        params=(P("job_id", "string", required=True, desc="Compliance job id."),),
        output="json",
        scopes=(),
    ),
    T(
        "upload_compliance_submission",
        "PUT",
        "/2/compliance/jobs/{job_id}/upload",
        "Upload the ids to remove for a compliance job.",
        family="Compliance",
        params=(
            P("job_id", "string", required=True, desc="Compliance job id."),
            P("file_name", "string", required=True, desc="File name of the upload."),
            P("file_base64", "string", desc="Base64 encoded file content."),
            P("ids", "array", desc="Ids to remove (alternative to a file upload)."),
        ),
        body=("file_name", "file_base64", "ids"),
        output="json",
        scopes=(),
    ),
    T(
        "get_developer_account",
        "GET",
        "/2/account",
        "Get the developer account behind the app.",
        family="Account",
        params=(),
        output="json",
        scopes=("developer.read",),
    ),
    T(
        "get_usage",
        "GET",
        "/2/usage/tweets",
        "Get the current usage of the application.",
        family="Usage",
        params=(),
        output="json",
        scopes=(),
    ),
    T(
        "get_usage_credits",
        "GET",
        "/2/usage/credits",
        "Get the remaining usage credits.",
        family="Usage",
        params=(),
        output="json",
        scopes=(),
    ),
)

# --------------------------------------------------------------------------
# Streams, webhooks, activity subscriptions
# --------------------------------------------------------------------------
add(
    T(
        "get_stream_rules",
        "GET",
        "/2/tweets/search/stream/rules",
        "List the rules of the filtered stream.",
        family="Stream",
        params=(),
        output="json",
        scopes=(),
    ),
    T(
        "update_stream_rules",
        "POST",
        "/2/tweets/search/stream/rules",
        "Add or remove filtered stream rules.",
        family="Stream",
        params=(
            P("add", "array", desc="Rules to add, each with a value."),
            P("remove", "array", desc="Rule ids to remove."),
        ),
        body=("add", "remove"),
        output="json",
        scopes=(),
    ),
    T(
        "get_rule_counts",
        "GET",
        "/2/tweets/search/stream/rules/counts",
        "Get the number of filtered stream rules in use.",
        family="Stream",
        params=(),
        output="json",
        scopes=(),
    ),
    T(
        "create_webhook",
        "POST",
        "/2/webhooks",
        "Create an activity webhook.",
        family="Webhooks",
        params=(
            P("url", "string", required=True, desc="Callback URL."),
            P("events", "array", desc="Event types to subscribe to."),
            P("filter", "object", desc="Event filter payload."),
        ),
        body=("url", "events", "filter"),
        output="json",
        scopes=(),
    ),
    T(
        "list_webhooks",
        "GET",
        "/2/webhooks",
        "List the webhooks of the application.",
        family="Webhooks",
        params=(),
        output="json",
        scopes=(),
    ),
    T(
        "delete_webhook",
        "DELETE",
        "/2/webhooks/{webhook_id}",
        "Delete a webhook.",
        family="Webhooks",
        params=(P("webhook_id", "string", required=True, desc="Webhook id."),),
        output="success",
        scopes=(),
    ),
    T(
        "validate_webhook",
        "PUT",
        "/2/webhooks/{webhook_id}",
        "Validate a webhook by challenge check.",
        family="Webhooks",
        params=(P("webhook_id", "string", required=True, desc="Webhook id."),),
        output="json",
        scopes=(),
    ),
    T(
        "create_replay_job",
        "POST",
        "/2/webhooks/replay",
        "Replay events to a webhook.",
        family="Webhooks",
        params=(
            P("webhook_id", "string", required=True, desc="Webhook id."),
            P("from", "string", desc="Start time of the replay window."),
            P("to", "string", desc="End time of the replay window."),
        ),
        body=("webhook_id", "from", "to"),
        output="json",
        scopes=(),
    ),
    T(
        "get_stream_links",
        "GET",
        "/2/tweets/search/webhooks",
        "List filtered stream webhook links.",
        family="Webhooks",
        params=(),
        output="json",
        scopes=(),
    ),
    T(
        "create_stream_link",
        "POST",
        "/2/tweets/search/webhooks/{webhook_id}",
        "Create a filtered stream webhook link.",
        family="Webhooks",
        params=(P("webhook_id", "string", required=True, desc="Webhook id."),),
        output="json",
        scopes=(),
    ),
    T(
        "delete_stream_link",
        "DELETE",
        "/2/tweets/search/webhooks/{webhook_id}",
        "Delete a filtered stream webhook link.",
        family="Webhooks",
        params=(P("webhook_id", "string", required=True, desc="Webhook id."),),
        output="success",
        scopes=(),
    ),
    T(
        "create_activity_subscription",
        "POST",
        "/2/activity/subscriptions",
        "Subscribe to X Activity events for users.",
        family="Activity",
        params=(
            P("user_ids", "array", required=True, desc="User ids to subscribe to."),
            P("event_types", "array", desc="Event types, e.g. like, follow."),
            P("activity_types", "array", desc="Activity types, e.g. Subscribe, like."),
            P("subscription_name", "string", desc="Name of the subscription."),
        ),
        body=("user_ids", "event_types", "activity_types", "subscription_name"),
        output="json",
        scopes=("like.read", "tweet.read"),
    ),
    T(
        "list_activity_subscriptions",
        "GET",
        "/2/activity/subscriptions",
        "List the X Activity subscriptions.",
        family="Activity",
        params=(),
        output="json",
        scopes=("like.read", "tweet.read"),
    ),
    T(
        "update_activity_subscription",
        "PUT",
        "/2/activity/subscriptions/{subscription_id}",
        "Update an X Activity subscription.",
        family="Activity",
        params=(
            P("subscription_id", "string", required=True, desc="Subscription id."),
            P("user_ids", "array", desc="User ids."),
            P("event_types", "array", desc="Event types."),
            P("activity_types", "array", desc="Activity types."),
        ),
        body=("user_ids", "event_types", "activity_types"),
        output="json",
        scopes=(),
    ),
    T(
        "delete_activity_subscription",
        "DELETE",
        "/2/activity/subscriptions/{subscription_id}",
        "Delete an X Activity subscription.",
        family="Activity",
        params=(P("subscription_id", "string", required=True, desc="Subscription id."),),
        output="success",
        scopes=(),
    ),
    T(
        "create_account_activity_subscription",
        "POST",
        "/2/account_activity/webhooks/{webhook_id}/subscriptions/all",
        "Subscribe a user to an Account Activity webhook.",
        family="Account Activity",
        params=(
            P("webhook_id", "string", required=True, desc="Webhook id."),
            P("user_id", "string", required=True, desc="User id to subscribe."),
            P("activities", "array", desc="Activity types to subscribe to."),
            P("all_activity", "boolean", desc="Subscribe to every activity type."),
        ),
        body=("user_id", "activities", "all_activity"),
        output="json",
        scopes=("dm.read", "dm.write", "tweet.read", "users.read"),
    ),
    T(
        "list_account_activity_subscriptions",
        "GET",
        "/2/account_activity/webhooks/{webhook_id}/subscriptions/all/list",
        "List the subscriptions of an Account Activity webhook.",
        family="Account Activity",
        params=(P("webhook_id", "string", required=True, desc="Webhook id."),),
        output="json",
        scopes=(),
    ),
    T(
        "validate_account_activity_subscription",
        "GET",
        "/2/account_activity/webhooks/{webhook_id}/subscriptions/all",
        "Validate an Account Activity subscription.",
        family="Account Activity",
        params=(P("webhook_id", "string", required=True, desc="Webhook id."),),
        output="json",
        scopes=("dm.read", "dm.write", "tweet.read", "users.read"),
    ),
    T(
        "delete_account_activity_subscription",
        "DELETE",
        "/2/account_activity/webhooks/{webhook_id}/subscriptions/{user_id}/all",
        "Delete an Account Activity subscription.",
        family="Account Activity",
        params=(
            P("webhook_id", "string", required=True, desc="Webhook id."),
            P("user_id", "string", required=True, desc="Subscribed user id."),
        ),
        output="success",
        scopes=(),
    ),
    T(
        "get_account_activity_subscription_count",
        "GET",
        "/2/account_activity/subscriptions/count",
        "Get the number of Account Activity subscriptions.",
        family="Account Activity",
        params=(),
        output="json",
        scopes=(),
    ),
)

# --------------------------------------------------------------------------
# Broadcasts, calls, bots, articles
# --------------------------------------------------------------------------
add(
    T(
        "list_broadcasts",
        "GET",
        "/2/broadcasts",
        "List the broadcasts of the application.",
        family="Broadcasts",
        params=paging(10, 100),
        output="json",
        scopes=("broadcast.read",),
    ),
    T(
        "get_broadcast",
        "GET",
        "/2/broadcasts/{broadcast_id}",
        "Get a broadcast by id.",
        family="Broadcasts",
        params=(P("broadcast_id", "string", required=True, desc="Broadcast id."),),
        output="json",
        scopes=("broadcast.read",),
    ),
    T(
        "delete_broadcast",
        "DELETE",
        "/2/broadcasts/{broadcast_id}",
        "Delete a broadcast.",
        family="Broadcasts",
        params=(P("broadcast_id", "string", required=True, desc="Broadcast id."),),
        output="success",
        scopes=("broadcast.read", "broadcast.write"),
    ),
    T(
        "get_broadcast_chat",
        "GET",
        "/2/broadcasts/{broadcast_id}/chat",
        "Get the chat history of a broadcast.",
        family="Broadcasts",
        params=(
            P("broadcast_id", "string", required=True, desc="Broadcast id."),
            P("max_results", "integer", desc="Number of messages.", default=100, minimum=1, maximum=100),
            P("pagination_token", "string", desc="Pagination token."),
        ),
        output="json",
        scopes=("broadcast.read",),
    ),
    T(
        "send_broadcast_chat",
        "POST",
        "/2/broadcasts/{broadcast_id}/chat",
        "Send a chat message in a broadcast.",
        family="Broadcasts",
        params=(
            P("broadcast_id", "string", required=True, desc="Broadcast id."),
            P("text", "string", required=True, desc="Message text."),
        ),
        body=("text",),
        output="json",
        scopes=("broadcast.read", "broadcast.write"),
    ),
    T(
        "list_scheduled_broadcasts",
        "GET",
        "/2/broadcasts/scheduled",
        "List the scheduled broadcasts.",
        family="Broadcasts",
        params=paging(10, 100),
        output="json",
        scopes=("broadcast.read",),
    ),
    T(
        "create_scheduled_broadcast",
        "POST",
        "/2/broadcasts/scheduled",
        "Schedule a broadcast.",
        family="Broadcasts",
        params=(
            P("start_time", "string", desc="ISO 8601 start time."),
            P("end_time", "string", desc="ISO 8601 end time."),
            P("auto_delete", "boolean", desc="Delete the broadcast after it ends."),
        ),
        body=("start_time", "end_time", "auto_delete"),
        output="json",
        scopes=("broadcast.read", "broadcast.write"),
    ),
    T(
        "get_scheduled_broadcast",
        "GET",
        "/2/broadcasts/scheduled/{broadcast_id}",
        "Get a scheduled broadcast.",
        family="Broadcasts",
        params=(P("broadcast_id", "string", required=True, desc="Broadcast id."),),
        output="json",
        scopes=("broadcast.read",),
    ),
    T(
        "delete_scheduled_broadcast",
        "DELETE",
        "/2/broadcasts/scheduled/{broadcast_id}",
        "Delete a scheduled broadcast.",
        family="Broadcasts",
        params=(P("broadcast_id", "string", required=True, desc="Broadcast id."),),
        output="success",
        scopes=("broadcast.read", "broadcast.write"),
    ),
    T(
        "go_live_scheduled_broadcast",
        "POST",
        "/2/broadcasts/scheduled/{broadcast_id}/live",
        "Take a scheduled broadcast live.",
        family="Broadcasts",
        params=(P("broadcast_id", "string", required=True, desc="Broadcast id."),),
        output="json",
        scopes=("broadcast.read", "broadcast.write"),
    ),
    T(
        "list_calls",
        "GET",
        "/2/calls/scheduled",
        "List the scheduled calls of the application.",
        family="Calls",
        params=paging(10, 100),
        output="json",
        scopes=("calls.read",),
    ),
    T(
        "get_call",
        "GET",
        "/2/calls/{call_id}",
        "Get a call by id.",
        family="Calls",
        params=(P("call_id", "string", required=True, desc="Call id."),),
        output="json",
        scopes=("calls.read",),
    ),
    T(
        "schedule_call",
        "POST",
        "/2/calls/scheduled",
        "Schedule a call.",
        family="Calls",
        params=(
            P("participant_ids", "array", required=True, desc="Participant user ids."),
            P("start_time", "string", desc="ISO 8601 start time."),
            P("end_time", "string", desc="ISO 8601 end time."),
            P("title", "string", desc="Call title."),
        ),
        body=("participant_ids", "start_time", "end_time", "title"),
        output="json",
        scopes=("calls.write",),
    ),
    T(
        "cancel_scheduled_call",
        "DELETE",
        "/2/calls/scheduled/{call_id}",
        "Cancel a scheduled call.",
        family="Calls",
        params=(P("call_id", "string", required=True, desc="Call id."),),
        output="success",
        scopes=("calls.write",),
    ),
    T(
        "list_bots",
        "GET",
        "/2/bots",
        "List the bots of the application.",
        family="Bots",
        params=paging(10, 100),
        output="json",
        scopes=(),
    ),
    T(
        "create_bot",
        "POST",
        "/2/bots",
        "Create a bot.",
        family="Bots",
        params=(
            P("name", "string", desc="Bot name."),
            P("description", "string", desc="Bot description."),
            P("handle", "string", desc="Bot handle."),
        ),
        body=("name", "description", "handle"),
        output="json",
        scopes=(),
    ),
    T(
        "delete_bot",
        "DELETE",
        "/2/bots/{bot_id}",
        "Delete a bot.",
        family="Bots",
        params=(P("bot_id", "string", required=True, desc="Bot id."),),
        output="success",
        scopes=(),
    ),
    T(
        "create_article_draft",
        "POST",
        "/2/articles/draft",
        "Create an article draft.",
        family="Articles",
        params=(
            P("title", "string", required=True, desc="Article title."),
            P("body", "string", desc="Article body."),
        ),
        body=("title", "body"),
        output="json",
        scopes=(),
    ),
    T(
        "publish_article",
        "POST",
        "/2/articles/{article_id}/publish",
        "Publish an article draft.",
        family="Articles",
        params=(P("article_id", "string", required=True, desc="Article id."),),
        output="json",
        scopes=("tweet.write",),
    ),
)

# --------------------------------------------------------------------------
# Escape hatch - reaches every remaining documented operation
# --------------------------------------------------------------------------
add(
    T(
        "x_api_request",
        "GET",
        "/2/",
        "Call any X API v2 operation directly. Use this for endpoints that do not have a dedicated tool "
        "(compliance batch, public keys, DM media, streaming rules of other apps, Enterprise analytics, ...). "
        "The path is relative to https://api.x.com and must start with /2/, /1.1/ or /oauth2/.",
        family="General",
        auth="auto",
        params=(
            P("method", "string", required=True, desc="HTTP method.", enum=("GET", "POST", "PUT", "DELETE", "PATCH")),
            P("path", "string", required=True, desc="Path relative to https://api.x.com, e.g. /2/users/123/liked_tweets."),
            P("query", "object", desc="Query string parameters as an object."),
            P("body", "object", desc="JSON request body."),
            P("auth", "string", desc="Authentication transport to use.", enum=("auto", "oauth1", "oauth2"), default="auto"),
        ),
        body=(),
        output="json",
        scopes=(),
    ),
)

from .api_extended import EXTRA_TOOLS  # noqa: E402  (late import avoids a circular dependency)

TOOLS.extend(EXTRA_TOOLS)
TOOL_INDEX: dict[str, Tool] = {t.name: t for t in TOOLS}
