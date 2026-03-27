"""Core module - Generic bot logic (reusable with any interface).

This module contains the core bot functionality that is independent
of any specific messaging platform (Slack, Discord, Web API, etc.)
"""

from .bot import OnboardingBot
from .config import config


# Lazy import for FirestoreConversationStore to avoid import errors
# when google-cloud-firestore is not installed (e.g., local testing)
def get_firestore_store() -> type:
    """Lazy import FirestoreConversationStore to avoid import errors."""
    from .storage import FirestoreConversationStore

    return FirestoreConversationStore


__all__ = ["OnboardingBot", "config", "get_firestore_store"]
