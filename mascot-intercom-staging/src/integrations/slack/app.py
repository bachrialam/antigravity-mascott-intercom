"""Slack Integration - FastAPI Application.

This is the entry point for the Slack bot integration.
It sets up FastAPI, Slack Bolt, and coordinates all components.

To run:
    python -m src.integrations.slack.app

Architecture:
    Slack Event → FastAPI → Handler → RAG Retrieval → OpenAI → Response
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from dotenv import load_dotenv

# Load environment variables from .env file FIRST (before importing config)
load_dotenv()

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from slack_bolt.adapter.fastapi.async_handler import (  # noqa: E402
    AsyncSlackRequestHandler,
)
from slack_bolt.async_app import AsyncApp  # noqa: E402

from ...core.bot import OnboardingBot  # noqa: E402
from ...core.config import config  # noqa: E402
from ...core.storage import FirestoreConversationStore  # noqa: E402
from ..intercom.webhook import process_intercom_webhook  # noqa: E402
from .config import slack_config  # noqa: E402
from .handlers import SlackEventHandler  # noqa: E402

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.DEBUG if config.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# COMPONENT INITIALIZATION
# =============================================================================

# Initialize Slack app with bot token and signing secret
slack_app = AsyncApp(
    token=slack_config.slack_bot_token,
    signing_secret=slack_config.slack_signing_secret,
)
logger.info("✅ Slack app initialized")

# Create bot instance (this connects to Weaviate)
onboarding_bot = OnboardingBot()

# Initialize Firestore conversation store
conversation_store = FirestoreConversationStore(
    project_id=config.bigquery_project, collection_name="onboarding_conversations"
)

# Create event handler that will process Slack events
event_handler = SlackEventHandler(onboarding_bot, conversation_store)

# Register Slack event handlers
slack_app.event("app_mention")(event_handler.handle_app_mention)
slack_app.event("message")(event_handler.handle_message)

# Initialize Slack request handler for FastAPI
app_handler = AsyncSlackRequestHandler(slack_app)


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events."""
    # STARTUP
    logger.info("=" * 80)
    logger.info("🚀 Kittl Onboarding Assistant Starting Up (Slack Integration)")
    logger.info("=" * 80)
    logger.info(f"Environment: {config.environment}")
    logger.info(f"OpenAI Model: {config.openai_model}")
    logger.info(f"Weaviate URL: {config.weaviate_url}")
    logger.info(f"Weaviate Collection: {config.weaviate_collection}")
    logger.info(f"RAG Top-K: {config.rag_top_k}")
    logger.info(f"Host: {config.host}:{config.port}")
    logger.info("=" * 80)

    # Validate configuration
    try:
        config.validate()
        logger.info("✅ Configuration validated successfully")
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        raise

    yield  # Application runs here

    # SHUTDOWN
    logger.info("=" * 80)
    logger.info("🛑 Kittl Onboarding Assistant Shutting Down")
    logger.info("=" * 80)

    onboarding_bot.close()
    logger.info("✅ Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Kittl Onboarding Assistant (Slack)",
    description="AI-powered Slack bot for helping users learn Kittl tools",
    version="1.0.0",
    lifespan=lifespan,
)


# =============================================================================
# API ENDPOINTS
# =============================================================================

# Event deduplication: Track processed event IDs to prevent duplicate processing
processed_events: set = set()


@app.post("/slack/events", response_model=None)
async def slack_events(request: Request) -> Response | dict:
    """Main endpoint for Slack event webhooks.

    Slack sends POST requests here whenever an event happens (mentions, DMs, etc.). This
    endpoint IMMEDIATELY returns 200 OK to prevent Slack retries, then processes the
    event in the background.
    """
    try:
        body = await request.json()

        # URL verification challenge - must respond immediately
        if body.get("type") == "url_verification":
            logger.info("🔐 Slack URL verification challenge received")
            return {"challenge": body.get("challenge")}

        # Event deduplication
        event_id = body.get("event_id") or body.get("event", {}).get("client_msg_id")
        if event_id and event_id in processed_events:
            logger.info(f"⚠️ Duplicate event {event_id}, skipping")
            return Response(status_code=200)

        # Mark event as processed
        if event_id:
            processed_events.add(event_id)
            if len(processed_events) > 1000:
                processed_events.pop()

        # Acknowledge Slack IMMEDIATELY (< 3s to prevent retries)
        logger.info(
            f"✅ Acknowledged Slack event {event_id}, processing in background..."
        )

        # Process event in background (non-blocking)
        asyncio.create_task(app_handler.handle(request))

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"❌ Error handling Slack event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for monitoring and load balancers."""
    return {
        "status": "healthy",
        "service": "onboarding-assistant",
        "integration": "slack",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "weaviate": "connected",
            "openai": "configured",
            "slack": "configured",
            "firestore": "configured",
        },
    }


@app.post("/intercom/webhook", status_code=200)
async def intercom_webhook(request: Request) -> dict:
    """Intercom webhook endpoint (staging only). Accepts payload, extracts message, sends to mascot core."""
    try:
        body = await request.json()
    except Exception:
        return {}
    if isinstance(body, dict):
        process_intercom_webhook(onboarding_bot, body)
    return {"ok": True}


@app.get("/")
async def root() -> dict:
    """Root endpoint with service information."""
    return {
        "service": "Kittl Onboarding Assistant",
        "integration": "Slack",
        "description": "AI-powered Slack bot for onboarding help",
        "version": "1.0.0",
        "endpoints": {
            "slack_events": "/slack/events",
            "intercom_webhook": "/intercom/webhook",
            "health": "/health",
            "docs": "/docs",
        },
    }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main() -> None:
    """Main entry point when running the script directly."""
    import uvicorn

    logger.info(f"🚀 Starting server at http://{config.host}:{config.port}")
    logger.info(f"📚 API docs available at http://{config.host}:{config.port}/docs")

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="debug" if config.debug else "info",
    )


if __name__ == "__main__":
    main()
