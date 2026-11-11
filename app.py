"""Vercel's ASGI entry point."""

from fastapi import FastAPI
from starlette.responses import JSONResponse

from src.twitter_mcp.config import load_config
from src.twitter_mcp.server import create_app

app = FastAPI(openapi_url=None)

try:
    config = load_config()
except RuntimeError:
    @app.get("/health")
    @app.api_route("/mcp", methods=["POST", "GET", "DELETE"])
    async def unconfigured() -> JSONResponse:
        return JSONResponse({"status": "unconfigured"}, status_code=503)
else:
    app.mount("/", create_app(config, require_mcp_token=True))
