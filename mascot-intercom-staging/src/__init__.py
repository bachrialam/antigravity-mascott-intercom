"""Onboarding Mascot - AI-powered assistant for Kittl onboarding.

Package Structure:
    src/
    ├── core/                 # Generic bot logic (reusable)
    │   ├── bot.py           # OnboardingBot class
    │   ├── storage.py       # Firestore conversation storage
    │   └── config.py        # Core configuration
    │
    ├── integrations/         # Platform-specific implementations
    │   └── slack/           # Slack bot integration
    │       ├── app.py       # FastAPI + Slack setup
    │       ├── handlers.py  # Slack event handlers
    │       └── config.py    # Slack-specific config
    │
    ├── rag/                  # RAG (Retrieval Augmented Generation)
    │   ├── retriever.py     # Weaviate retriever
    │   └── models.py        # Data models
    │
    └── config/
        └── system_prompt.txt # LLM personality/behavior

Usage:
    # Run Slack integration
    python -m src.integrations.slack.app

    # Or use the core bot directly
    from src.core import OnboardingBot
    bot = OnboardingBot()
"""
