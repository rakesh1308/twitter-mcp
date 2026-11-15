"""Vercel entrypoint: expose the MCP server as a serverless ASGI function."""

import pathlib
import sys

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from twitter_mcp.server import app  # noqa: E402

__all__ = ["app"]
