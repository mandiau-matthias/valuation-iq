"""ASGI entrypoint for the ValuationIQ API."""

import os

import uvicorn

from src.api.app_factory import create_app
from src.config import resolve_default_server_host

app, readiness = create_app()


def _dev_server_host() -> str:
    return resolve_default_server_host()


if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=_dev_server_host(),
        port=int(os.environ.get("PORT", "8080")),
        reload=True,
        log_level="info",
    )
