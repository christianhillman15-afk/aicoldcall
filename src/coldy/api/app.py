"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from ..config import settings
from ..logging import get_logger
from .routes import dashboard, health, media, optin, twilio_webhooks

log = get_logger("coldy.api")


def create_app() -> FastAPI:
    app = FastAPI(title="Coldy", version="0.1.0")

    app.include_router(health.router)
    app.include_router(twilio_webhooks.router)
    app.include_router(media.router)
    app.include_router(dashboard.router)
    app.include_router(optin.router)

    @app.on_event("startup")
    async def _startup() -> None:
        from ..db.session import init_db

        init_db()
        log.info("Coldy API up. Public base: %s", settings.public_base_url)

    return app


app = create_app()
