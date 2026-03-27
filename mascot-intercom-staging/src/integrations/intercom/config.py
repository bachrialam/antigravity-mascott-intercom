"""Intercom-Specific Configuration.

This module contains configuration settings specific to the Intercom integration.
Core settings (OpenAI, Weaviate, etc.) are in core/config.py
"""

import os


class IntercomConfig:
    """Intercom-specific configuration.

    Load INTERCOM_TOKEN and INTERCOM_ADMIN_ID from environment variables.
    Set these in .env when using Intercom (e.g. for API calls or replying to conversations).
    """

    def __init__(self) -> None:
        """Initialize Intercom configuration from environment variables."""
        # Access token for Intercom API (e.g. from Intercom Developer Hub)
        self.intercom_token = os.getenv("INTERCOM_TOKEN")

        # Admin/workspace ID (or agent ID) used when posting replies as the bot
        self.intercom_admin_id = os.getenv("INTERCOM_ADMIN_ID")

    def validate(self) -> None:
        """Validate that Intercom credentials are set when using Intercom features.

        Raises:
            ValueError: If INTERCOM_TOKEN or INTERCOM_ADMIN_ID is missing.
        """
        if not self.intercom_token:
            raise ValueError(
                "INTERCOM_TOKEN environment variable is required for Intercom integration"
            )
        if not self.intercom_admin_id:
            raise ValueError(
                "INTERCOM_ADMIN_ID environment variable is required for Intercom integration"
            )

    @property
    def is_configured(self) -> bool:
        """Return True if both token and admin ID are set."""
        return bool(self.intercom_token and self.intercom_admin_id)

    def __repr__(self) -> str:
        """String representation (masks sensitive data)."""
        token = "***" + (self.intercom_token[-8:] if self.intercom_token else "")
        return (
            "IntercomConfig(\n"
            f"  intercom_token={token},\n"
            f"  intercom_admin_id={self.intercom_admin_id}\n"
            ")"
        )


# Create global Intercom config instance
intercom_config = IntercomConfig()
