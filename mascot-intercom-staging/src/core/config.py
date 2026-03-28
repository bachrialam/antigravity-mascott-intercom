"""Core Configuration Management.

This module centralizes all configuration settings for the Onboarding Bot,
including API keys, environment variables, and application settings.

This config is platform-agnostic (no Slack-specific settings).
Slack-specific config lives in integrations/slack/config.py
"""

import os
from pathlib import Path

# Load .env dari root project dulu (agar jalan dengan: python -m src.integrations.intercom.app)
from dotenv import load_dotenv
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")


class CoreConfig:
    """Core configuration class for the Onboarding Assistant.

    This loads all settings from environment variables and provides
    sensible defaults where appropriate.

    Note: Slack-specific config (tokens, secrets) is in integrations/slack/config.py
    """

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        # ============================================================================
        # OPENAI CONFIGURATION
        # ============================================================================

        # OpenAI API key for LLM calls
        self.openai_api_key = os.getenv("OPENAI_API_KEY_DATA_BOT")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY_DATA_BOT environment variable is required")

        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # ============================================================================
        # WEAVIATE CONFIGURATION
        # ============================================================================

        # Weaviate Cloud cluster URL (without https://)
        self.weaviate_url = os.getenv("WEAVIATE_URL")
        if not self.weaviate_url:
            raise ValueError("WEAVIATE_URL environment variable is required")

        # Weaviate API key for authentication
        self.weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
        if not self.weaviate_api_key:
            raise ValueError("WEAVIATE_API_KEY environment variable is required")

        # Name of the Weaviate collection containing documentation chunks
        self.weaviate_collection = os.getenv(
            "WEAVIATE_COLLECTION", "MascotHelpArticlesV2"
        )

        # Number of documentation chunks to retrieve for context
        self.rag_top_k = int(os.getenv("RAG_TOP_K", "5"))

        # Minimum similarity threshold for including chunks (0.0 - 1.0)
        self.rag_similarity_threshold = float(
            os.getenv("RAG_SIMILARITY_THRESHOLD", "0.4")
        )

        # ============================================================================
        # SERVER CONFIGURATION
        # ============================================================================

        # Host to bind the server to
        # 0.0.0.0 = listen on all interfaces (needed for Cloud Run)
        self.host = os.getenv("HOST", "0.0.0.0")

        # Port to run the server on
        # Cloud Run sets PORT automatically, default to 8080 for local dev
        self.port = int(os.getenv("PORT", "8080"))

        # ============================================================================
        # APPLICATION SETTINGS
        # ============================================================================

        # Path to system prompt file
        # This defines the bot's personality and behavior
        self.system_prompt_file = self._get_system_prompt_path()

        # Enable debug logging (more verbose output)
        self.debug = os.getenv("DEBUG", "false").lower() == "true"

        # Environment name (dev, staging, production)
        self.environment = os.getenv("ENVIRONMENT", "development")

        # ============================================================================
        # BIGQUERY CONFIGURATION
        # ============================================================================

        # Service account credentials for BigQuery access
        self.bigquery_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        # BigQuery project from environment
        self.bigquery_project = os.getenv("GOOGLE_CLOUD_PROJECT")

        # BigQuery dataset and table (hardcoded) for writing metrics to BigQuery
        self.bigquery_dataset = "prod_el"
        self.bigquery_table = "onboarding_mascot_metrics"

        # Enable BigQuery logging
        self.enable_bigquery_logging = True

    def _get_system_prompt_path(self) -> Path:
        """Find the system prompt file, checking multiple possible locations.

        Returns:
            Path to system_prompt.txt
        """
        # Allow override via environment variable
        env_path = os.getenv("SYSTEM_PROMPT_FILE")
        if env_path:
            # Try as absolute path first, then relative to project root
            path = Path(env_path)
            if path.exists():
                return path
            
            # Try relative to src/config if just filename is given
            relative_path = Path(__file__).parent.parent / "config" / env_path
            if relative_path.exists():
                return relative_path

        possible_paths = [
            Path(__file__).parent.parent
            / "config"
            / "system_prompt.txt",  # src/config/
            Path(__file__).parent / "system_prompt.txt",  # src/core/
            Path("src/config/system_prompt.txt"),  # Relative
            Path("system_prompt.txt"),  # Current directory
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Return first path as default (will error later if not found)
        return possible_paths[0]

    def validate(self) -> None:
        """Validate that all required configuration is present and correct.

        Raises:
            ValueError: If any required configuration is missing or invalid
        """
        # Check that system prompt file exists
        if not self.system_prompt_file.exists():
            raise ValueError(
                f"System prompt file not found at: {self.system_prompt_file}\n"
                "Please create src/config/system_prompt.txt"
            )

        # Validate numeric ranges
        if self.rag_top_k < 1 or self.rag_top_k > 10:
            raise ValueError("RAG_TOP_K must be between 1 and 10")

        if self.rag_similarity_threshold < 0.0 or self.rag_similarity_threshold > 1.0:
            raise ValueError("RAG_SIMILARITY_THRESHOLD must be between 0.0 and 1.0")

    def __repr__(self) -> str:
        """String representation (masks sensitive data)."""
        return (
            "CoreConfig(\n"
            f"  environment={self.environment},\n"
            f"  openai_model={self.openai_model},\n"
            f"  weaviate_url={self.weaviate_url},\n"
            f"  weaviate_collection={self.weaviate_collection},\n"
            f"  rag_top_k={self.rag_top_k},\n"
            f"  rag_similarity_threshold={self.rag_similarity_threshold},\n"
            f"  host={self.host},\n"
            f"  port={self.port}\n"
            ")"
        )


# Create global config instance
config = CoreConfig()
