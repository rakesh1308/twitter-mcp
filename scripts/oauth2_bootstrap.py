"""Mint an X OAuth 2.0 access + refresh token pair (authorization code + PKCE).

Usage:
    python scripts/oauth2_bootstrap.py --client-id <CLIENT_ID> --client-secret <CLIENT_SECRET>

The script prints an authorization URL. Open it, sign in, approve the app and
paste the full redirect URL (or just the code) back into the prompt. It then
exchanges the code for an access token and a refresh token and prints the
environment variables to copy into Vercel.

The redirect URI must be registered for the app in the developer portal; by
default https://localhost/callback is used, so a local redirect handler is
started for you.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

TOKEN_URL = "https://api.x.com/2/oauth2/token"
DEFAULT_SCOPE = (
    "tweet.read tweet.write tweet.moderate.write users.read follows.read follows.write "
    "like.read like.write list.read list.write bookmark.read bookmark.write media.write "
    "mute.read mute.write block.read block.write dm.read dm.write space.read offline.access"
)


def make_pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def start_redirect_handler(port: int) -> http.server.HTTPServer:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = (params.get("code") or [""])[0]
            body = "<html><body><h2>Authorization complete</h2><p>You can close this tab.</p></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode())
            self.server.code = code  # type: ignore[attr-defined]

        def log_message(self, *args: object) -> None:
            return

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    server.code = ""  # type: ignore[attr-defined]
    return server


def exchange(client_id: str, client_secret: str, code: str, verifier: str, redirect_uri: str) -> dict:
    payload = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
    ).encode()
    request = urllib.request.Request(TOKEN_URL, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as err:
        sys.stderr.write(f"token exchange failed: {err.code} {err.read().decode(errors='replace')}\n")
        raise SystemExit(1)


def app_only_token(client_id: str, client_secret: str) -> str:
    payload = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode()
    request = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read()).get("access_token", "")


def check_credits(client_id: str, client_secret: str) -> None:
    """Report the pay-per-use credit balance - posting needs credits on X."""
    try:
        token = app_only_token(client_id, client_secret)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not mint an app-only token: {exc}")
        return
    request = urllib.request.Request(
        "https://api.x.com/2/usage/credits",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            print("Credit balance:", response.read().decode(errors="replace"))
    except urllib.error.HTTPError as err:
        print(f"Credit check failed: {err.code} {err.read().decode(errors='replace')[:300]}")
    except Exception as exc:  # noqa: BLE001
        print(f"Credit check failed: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap X OAuth 2.0 tokens")
    parser.add_argument("--client-id", default=os.getenv("TWITTER_OAUTH2_CLIENT_ID", ""))
    parser.add_argument("--client-secret", default=os.getenv("TWITTER_OAUTH2_CLIENT_SECRET", ""))
    parser.add_argument("--scope", default=os.getenv("TWITTER_OAUTH2_SCOPE", DEFAULT_SCOPE))
    parser.add_argument("--redirect-uri", default="http://localhost:8765/callback")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    # X expects a space separated scope list; accept commas or newlines too.
    args.scope = " ".join(args.scope.replace(",", " ").split())

    if not args.client_id or not args.client_secret:
        raise SystemExit("--client-id and --client-secret are required (or set TWITTER_OAUTH2_CLIENT_ID/SECRET)")

    verifier, challenge = make_pkce()
    state = secrets.token_urlsafe(24)
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": args.client_id,
            "redirect_uri": args.redirect_uri,
            "scope": args.scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    url = f"https://x.com/i/oauth2/authorize?{query}"
    print("Open this URL, sign in and approve the app:\n")
    print(url)
    print(f"\nRequested scopes ({len(args.scope.split())}): {args.scope}\n")
    print("Waiting for the redirect on http://localhost:%d/callback ..." % args.port)

    server = start_redirect_handler(args.port)
    try:
        import threading

        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        thread.join(timeout=300)
    finally:
        server.server_close()

    code = getattr(server, "code", "")
    if not code:
        raise SystemExit("No authorization code received. Paste the code manually next time.")

    body = exchange(args.client_id, args.client_secret, code, verifier, args.redirect_uri)
    tokens = body.get("value", body)
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    print("\nToken exchange succeeded.")
    print("\nAdd these to Vercel (vercel env add <NAME> production):\n")
    print(f"TWITTER_OAUTH2_CLIENT_ID={args.client_id}")
    print(f"TWITTER_OAUTH2_CLIENT_SECRET={args.client_secret}")
    print(f"TWITTER_OAUTH2_ACCESS_TOKEN={access_token}")
    print(f"TWITTER_OAUTH2_REFRESH_TOKEN={refresh_token}")
    print(f"TWITTER_OAUTH2_SCOPE={args.scope}")
    print(f"\nGranted scopes: {tokens.get('scope', args.scope)}")
    print("\nChecking the pay-per-use credit balance (posting needs credits):")
    check_credits(args.client_id, args.client_secret)


if __name__ == "__main__":
    main()