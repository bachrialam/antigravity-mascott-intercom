"""Firestore Conversation Storage.

This module implements a storage backend for conversation history using
Google Cloud Firestore. This enables the bot to maintain context across
multiple Cloud Run instances and server restarts.

This is a platform-agnostic storage layer - can be used with Slack,
Discord, Web API, etc.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from google.cloud import firestore

logger = logging.getLogger(__name__)


class FirestoreConversationStore:
    """Manages conversation history in Google Cloud Firestore.

    Structure:
    - Collection: "onboarding_conversations"
    - Document ID: "{channel_id}_{thread_ts}" (or custom conversation_id)
    - Fields:
        - created_at: timestamp
        - updated_at: timestamp
        - messages: List[Dict] -> [{"role": "user", "content": "..."}, ...]
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        collection_name: str = "onboarding_conversations",
    ) -> None:
        """Initialize the Firestore client.

        Args:
            project_id: GCP Project ID. If None, inferred from environment.
            collection_name: Firestore collection name for conversations.
        """
        try:
            self.db = firestore.Client(project=project_id)
            self.collection = self.db.collection(collection_name)
            logger.info(
                f"Firestore initialized. Project: {project_id or 'default'},"
                f" Collection: {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            # We don't raise here to allow app to start, but storage calls will fail
            self.db = None

    async def get_history(
        self, thread_key: str, limit: int = 10
    ) -> List[Dict[str, str]]:
        """Retrieve conversation history for a specific thread.

        Args:
            thread_key: Unique identifier for the thread (e.g. "C123_1678.123")
            limit: Max number of recent messages to retrieve (default 10)

        Returns:
            List of message dictionaries: [{"role": "user", "content": "..."}]
        """
        if not self.db:
            logger.warning("⚠️ Firestore not initialized, returning empty history")
            return []

        try:
            doc_ref = self.collection.document(thread_key)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                messages = data.get("messages", [])

                # Return only the most recent messages
                # Note: We store them in chronological order, so we take the last N
                return messages[-limit:]
            else:
                return []

        except Exception as e:
            logger.error(f"❌ Error retrieving history for {thread_key}: {e}")
            return []

    async def add_messages(
        self, thread_key: str, messages: List[Dict[str, str]]
    ) -> None:
        """Add new messages to the conversation history.

        Args:
            thread_key: Unique identifier for the thread
            messages: List of message dicts to add [{"role": "...", "content": "..."}]
        """
        if not self.db:
            logger.warning("⚠️ Firestore not initialized, skipping save")
            return

        try:
            doc_ref = self.collection.document(thread_key)

            # Use array_union to append messages atomically
            # This handles concurrent writes better than reading-then-writing
            doc_ref.set(
                {
                    "messages": firestore.ArrayUnion(messages),
                    "updated_at": datetime.utcnow(),
                    "created_at": firestore.SERVER_TIMESTAMP,  # Set if doc missing
                },
                merge=True,
            )

            logger.debug(f"💾 Saved {len(messages)} messages to {thread_key}")

        except Exception as e:
            logger.error(f"❌ Error saving messages to {thread_key}: {e}")

    async def clear_history(self, thread_key: str) -> None:
        """Delete conversation history for a thread."""
        if not self.db:
            return
        try:
            self.collection.document(thread_key).delete()
            logger.info(f"🗑️ Cleared history for {thread_key}")
        except Exception as e:
            logger.error(f"❌ Error clearing history: {e}")
