"""Slack Integration Module.

This module contains all Slack-specific code:
- Slack Bolt app configuration
- FastAPI endpoints for Slack webhooks
- Slack event handlers
"""

from .app import app, main
from .config import slack_config
from .handlers import SlackEventHandler

__all__ = ["app", "main", "SlackEventHandler", "slack_config"]
