"""Intercom integration - Webhook handler for staging only.

This module is completely separate from Slack. It provides:
- POST /intercom/webhook - Accept Intercom webhooks, extract message, send to mascot core.
- Intercom config (INTERCOM_TOKEN, INTERCOM_ADMIN_ID) for API calls / replying.
"""

from .config import intercom_config
from .webhook import extract_message_from_payload, process_intercom_webhook

__all__ = [
    "extract_message_from_payload",
    "intercom_config",
    "process_intercom_webhook",
]
