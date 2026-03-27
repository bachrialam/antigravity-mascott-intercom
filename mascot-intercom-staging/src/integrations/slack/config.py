"""Slack-Specific Configuration.

This module contains configuration settings specific to the Slack integration. Core
settings (OpenAI, Weaviate, etc.) are in core/config.py
"""

import os


class SlackConfig:
    """Slack-specific configuration.

    This class loads Slack-specific settings from environment variables.
    """

    def __init__(self) -> None:
        """Initialize Slack configuration from environment variables."""
        # Bot token for authentication (starts with xoxb-)
        self.slack_bot_token = os.getenv("ONBOARDING_SLACK_BOT_TOKEN")
        if not self.slack_bot_token:
            raise ValueError(
                "ONBOARDING_SLACK_BOT_TOKEN environment variable is required"
            )

        # Signing secret for verifying Slack requests
        self.slack_signing_secret = os.getenv("ONBOARDING_SLACK_SIGNING_SECRET")
        if not self.slack_signing_secret:
            raise ValueError(
                "ONBOARDING_SLACK_SIGNING_SECRET environment variable is required"
            )

    def __repr__(self) -> str:
        """String representation (masks sensitive data)."""
        token = "***" + self.slack_bot_token[-8:] if self.slack_bot_token else None
        secret = (
            "***" + self.slack_signing_secret[-4:]
            if self.slack_signing_secret
            else None
        )
        return (
            "SlackConfig(\n"
            f"  slack_bot_token={token},\n"
            f"  slack_signing_secret={secret}\n"
            ")"
        )


# Create global Slack config instance
slack_config = SlackConfig()
