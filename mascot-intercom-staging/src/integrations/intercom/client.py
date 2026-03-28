"""Intercom API Client.

Handles interactions with the Intercom API, specifically sending replies to conversations.
References: https://developers.intercom.com/docs/references/rest-api/api.intercom.io/conversations/reply/
"""

import logging
from typing import Any, Dict, Optional

import httpx

from .config import intercom_config

logger = logging.getLogger(__name__)


class IntercomClient:
    """Async client for Intercom API."""

    BASE_URL = "https://api.intercom.io"

    def __init__(self) -> None:
        """Initialize with config from environment."""
        self.config = intercom_config
        # Strip whitespace to prevent "Access Token Invalid" if accidentally copied with spaces
        token = self.config.intercom_token.strip() if self.config.intercom_token else ""
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def send_reply(self, conversation_id: str, message_body: str, reply_options: Optional[list] = None) -> bool:
        """Reply to a conversation as an admin (the bot).

        Args:
            conversation_id: The ID of the conversation to reply to.
            message_body: The text content of the reply (supports Markdown).
            reply_options: Optional list of dictionaries representing quick reply buttons.

        Returns:
            True if successful, False otherwise.
        """
        if not self.config.is_configured:
            logger.warning(
                "Intercom not configured (missing token/admin_id). "
                "Cannot send reply to conversation %s.",
                conversation_id,
            )
            return False

        try:
            import markdown
            # Convert Markdown to HTML for Intercom's rich text
            # Extensions like 'fenced_code', 'tables', and 'nl2br' are useful.
            # Using nl2br ensures single newlines become <br> tags without wrapping everything in separate <p> tags
            # in a way that breaks markdown syntax like links.
            html_body = markdown.markdown(message_body, extensions=['fenced_code', 'tables', 'nl2br'])
        except ImportError:
            logger.warning("Markdown library not found. Sending raw text to Intercom.")
            html_body = message_body

        url = f"{self.BASE_URL}/conversations/{conversation_id}/reply"
        
        # Payload for replying as an admin
        # message_type must be "quick_reply" if buttons are present, otherwise "comment"
        message_type = "quick_reply" if reply_options else "comment"
        
        payload = {
            "message_type": message_type,
            "type": "admin",
            "admin_id": self.config.intercom_admin_id,
            "body": html_body,
        }
        
        if reply_options:
            payload["reply_options"] = reply_options

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, headers=self.headers, json=payload, timeout=10.0
                )
                
            if response.status_code == 200:
                logger.info(
                    "✅ Intercom reply sent successfully to conversation %s",
                    conversation_id,
                )
                return True
            else:
                logger.error(
                    "❌ Failed to send Intercom reply (Status %s): %s",
                    response.status_code,
                    response.text,
                )
                return False

        except httpx.RequestError as e:
            logger.error(
                "❌ Network error sending Intercom reply: %s", e, exc_info=True
            )
            return False
        except Exception as e:
            logger.error(
                "❌ Unexpected error sending Intercom reply: %s", e, exc_info=True
            )
            return False
    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conversation details including message history.

        Args:
            conversation_id: The ID of the conversation to retrieve.

        Returns:
            Dict containing conversation details, or None if failed.
        """
        if not self.config.is_configured:
            return None

        url = f"{self.BASE_URL}/conversations/{conversation_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, headers=self.headers, timeout=10.0
                )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    "❌ Failed to get Intercom conversation %s (Status %s): %s",
                    conversation_id,
                    response.status_code,
                    response.text,
                )
                return None

        except Exception as e:
            logger.error(
                "❌ Error getting Intercom conversation %s: %s",
                conversation_id,
                e,
                exc_info=True,
            )
            return None

    async def assign_conversation(
        self, conversation_id: str, assignee_id: str = "0", message_body: Optional[str] = None
    ) -> bool:
        """Assign a conversation to a human admin or team (or unassigned).

        Args:
            conversation_id: The ID of the conversation to assign.
            assignee_id: The admin ID or team ID to assign to. If "0", assigns to Unassigned.
            message_body: Optional internal note to leave during assignment.

        Returns:
            True if successful, False otherwise.
        """
        if not self.config.is_configured:
            logger.warning(
                "Intercom not configured. Cannot assign conversation %s.", conversation_id
            )
            return False

        url = f"{self.BASE_URL}/conversations/{conversation_id}/reply"
        
        # Payload for assigning
        payload = {
            "message_type": "assignment",
            "type": "admin",
            "admin_id": self.config.intercom_admin_id,
            "assignee_id": assignee_id,
        }
        if message_body:
            payload["body"] = message_body

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, headers=self.headers, json=payload, timeout=10.0
                )
                
            if response.status_code == 200:
                logger.info(
                    "✅ Intercom conversation %s assigned successfully.",
                    conversation_id,
                )
                return True
            else:
                logger.error(
                    "❌ Failed to assign Intercom conversation %s (Status %s): %s",
                    conversation_id,
                    response.status_code,
                    response.text,
                )
                return False

        except httpx.RequestError as e:
            logger.error(
                "❌ Network error assigning Intercom conversation %s: %s", conversation_id, e, exc_info=True
            )
            return False
        except Exception as e:
            logger.error(
                "❌ Unexpected error assigning Intercom conversation %s: %s", conversation_id, e, exc_info=True
            )
            return False

# Global client instance
intercom_client = IntercomClient()
