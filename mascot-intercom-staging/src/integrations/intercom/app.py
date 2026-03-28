"""Intercom Integration - FastAPI Application (Intercom-only).

Entry point for deploying the Onboarding Mascot with Intercom only (no Slack).
Exposes POST /intercom/webhook for Intercom webhooks.

To run:
    python -m src.integrations.intercom.app
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv

# Load .env from project root (supaya jalan dari mana pun dijalankan)
_project_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_project_root / ".env")

from fastapi import FastAPI, Request, BackgroundTasks  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

from ...core.bot import OnboardingBot  # noqa: E402
from ...core.config import config  # noqa: E402
from .webhook import process_intercom_webhook  # noqa: E402

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.DEBUG if config.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# BOT (shared with webhook handler)
# =============================================================================

onboarding_bot = OnboardingBot()

# =============================================================================
# FASTAPI APP
# =============================================================================


@asynccontextmanager
async def lifespan(app):  # noqa: ARG001
    """Startup and shutdown."""
    logger.info("=" * 60)
    logger.info("Kittl Onboarding Mascot (Intercom-only) starting")
    logger.info("=" * 60)
    logger.info("Environment: %s", config.environment)
    logger.info("Weaviate: %s | Collection: %s", config.weaviate_url, config.weaviate_collection)
    logger.info("Host: %s:%s", config.host, config.port)
    logger.info("=" * 60)
    try:
        config.validate()
        logger.info("Configuration validated")
    except Exception as e:
        logger.error("Configuration validation failed: %s", e)
        raise
    yield
    logger.info("Shutting down...")
    onboarding_bot.close()
    logger.info("Shutdown complete")

app = FastAPI(
    title="Kittl Onboarding Mascot (Intercom)",
    description="AI onboarding assistant via Intercom webhooks",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict:
    """Service info."""
    return {
        "service": "Kittl Onboarding Mascot",
        "integration": "Intercom",
        "version": "1.0.0",
        "endpoints": {
            "intercom_webhook": "/intercom/webhook",
            "health": "/health",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health() -> dict:
    """Health check for Cloud Run and load balancers."""
    return {
        "status": "healthy",
        "service": "onboarding-mascot-intercom",
        "integration": "intercom",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/intercom/webhook", status_code=200)
async def intercom_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    """Accept Intercom webhooks; extract message and process with mascot core."""
    try:
        body = await request.json()
    except Exception:
        return {}
    if isinstance(body, dict):
        process_intercom_webhook(onboarding_bot, body, background_tasks)
    return {"ok": True}

@app.get("/test-widget")
async def test_widget() -> FileResponse:
    """Serve the Intercom test widget HTML file."""
    return FileResponse("docs/test_intercom_widget.html")


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Run the server."""
    import uvicorn

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="debug" if config.debug else "info",
    )


if __name__ == "__main__":
    main()
