# Onboarding Mascot

An AI-powered assistant that helps Kittl users learn about design tools through natural conversation. Built with RAG (Retrieval Augmented Generation) for accurate, documentation-grounded responses.

## What It Does

Users ask questions in Slack → Bot retrieves relevant documentation from Weaviate → OpenAI generates a helpful response → User gets an answer with video links and step-by-step instructions.

**Example:**
```
User: "How do I remove a background from an image?"
Bot: "You can use the AI Background Remover! Here's how:
      1. Select your image on the canvas
      2. Click 'Remove Background' in the properties panel
      3. The clipped image saves to your Clipped Images folder
      Watch the video: [link]"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         SLACK                                │
│                     (User Interface)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              integrations/slack/app.py                       │
│                  (FastAPI + Slack Bolt)                      │
│  • Receives Slack webhooks                                   │
│  • Handles @mentions and DMs                                 │
│  • Returns responses to Slack                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      core/bot.py                             │
│                   (OnboardingBot)                            │
│  • Builds prompts with RAG context                           │
│  • Calls OpenAI Responses API                                │
│  • Extracts token usage metrics                              │
└───────────┬─────────────────────────────────┬───────────────┘
            │                                 │
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────────┐
│    rag/retriever.py   │         │    core/storage.py        │
│      (Weaviate)       │         │      (Firestore)          │
│  • Semantic search    │         │  • Conversation history   │
│  • Dual-collection    │         │  • Enables multi-instance │
│    (Docs + Q&A pairs) │         │    scaling on Cloud Run   │
└───────────────────────┘         └───────────────────────────┘
```

---

## Project Structure

```
onboarding_mascot/
├── src/
│   ├── core/                          # Generic bot logic (platform-agnostic)
│   │   ├── bot.py                    # OnboardingBot - LLM integration
│   │   ├── config.py                 # OpenAI, Weaviate, BigQuery settings
│   │   └── storage.py                # Firestore conversation history
│   │
│   ├── integrations/                  # Platform-specific implementations
│   │   └── slack/
│   │       ├── app.py                # FastAPI + Slack Bolt entry point
│   │       ├── handlers.py           # Slack event handlers + BigQuery logging
│   │       └── config.py             # Slack tokens/secrets
│   │
│   ├── rag/                           # Retrieval Augmented Generation
│   │   ├── retriever.py              # Weaviate hybrid search
│   │   ├── models.py                 # RetrievedChunk, RAGResult, ProcessingMetrics
│   │   └── vector_store_updates/     # Legacy data preparation notebooks (moved to Dagster)
│   │       └── Onboarding Docs/      # Source .docx files
│   │
│   └── config/
│       └── system_prompt.txt         # Bot personality & response guidelines
│
├── docs/
│   └── README.md                     # This file
│
├── test_bot.ipynb                    # Local testing notebook
├── deploy.sh                         # Cloud Run deployment script
├── Dockerfile                        # Container configuration
└── requirements.txt                  # Project dependencies
```

---

## Key Components

### 1. RAG Retrieval (`rag/retriever.py`)

Queries **two Weaviate collections** simultaneously:
- `MascotHelpArticles` — Chunked documentation from .docx files
- `MascotQAPairs` — Previously answered customer support tickets

Uses **hybrid search** (80% semantic, 20% keyword) with similarity threshold filtering. Results from both collections are combined, sorted by similarity, and the top-K are returned.

### 2. Conversation Memory (`core/storage.py`)

Stores conversation history in **Google Cloud Firestore** (not in-memory), enabling:
- Multi-instance scaling on Cloud Run
- Context persistence across server restarts
- Thread-based conversation tracking (keyed by `{channel_id}_{thread_ts}`)

### 3. System Prompt (`config/system_prompt.txt`)

Defines the bot's behavior:
- Response tone and formatting (Slack-compatible markdown)
- Guardrails (pricing questions → pricing page, account issues → support)
- Fallback behavior when docs don't cover a topic
- Summary of Kittl's tools for generic questions

### 4. BigQuery Logging (`integrations/slack/handlers.py`)

Logs every interaction asynchronously to `kittl-data-platform.prod_el.onboarding_mascot_metrics`:
- User question and bot response
- Retrieved chunks with similarity scores
- Token breakdown (input, output, cached, reasoning)
- Latency metrics (retrieval time, LLM time, total time)

---

## Data Pipeline

### Preparing Documentation for Weaviate

The bot retrieves from two Weaviate collections managed via **Dagster**:

**1. MascotHelpArticles** — Managed by Dagster asset:
- Downloads .docx files from Google Drive (Onboarding Docs folder)
- Chunks by section headers (Tool Description, How to Use, etc.)
- Uploads to Weaviate with OpenAI embeddings
- Runs daily automatically (can be triggered manually via Dagster UI)

**2. MascotQAPairs** — Managed by Dagster asset:
- Queries Intercom conversations from BigQuery (last 90 days, resolved tickets)
- Formats as Q&A pairs for semantic matching
- Uploads to Weaviate with OpenAI embeddings
- Runs daily automatically (can be triggered manually via Dagster UI)

**When to manually trigger in Dagster:**
- Adding new documentation to Google Drive
- Major updates to existing docs that need immediate deployment
- Testing changes to the data pipeline

---

## Environment Setup

All configuration is managed via a `.env` file in the project directory.

### Quick Setup

```bash
# Copy the example and fill in your values
cp .env.example .env

# Edit .env with your credentials
```

### Required Variables

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `ONBOARDING_SLACK_BOT_TOKEN` | Bot OAuth Token (xoxb-...) | Slack App → OAuth |
| `ONBOARDING_SLACK_SIGNING_SECRET` | Request verification | Slack App → Basic Info |
| `OPENAI_API_KEY_DATA_BOT` | OpenAI API key | platform.openai.com |
| `WEAVIATE_URL` | Cluster URL (no https://) | Weaviate Console |
| `WEAVIATE_API_KEY` | Weaviate auth | Weaviate Console |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | GCP Console |

### For Updating Vector Store (Dagster)

The Weaviate data upload process has been migrated to **Dagster**. The required credentials for Google Drive access and BigQuery queries are configured in the Dagster environment, not in this service's `.env` file.

To update Weaviate collections, access the Dagster UI and trigger the relevant assets.

---

## Configuration

### Code Configuration (`core/config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `openai_model` | `gpt-5-mini` | LLM model |
| `rag_top_k` | `5` | Chunks to retrieve |
| `rag_similarity_threshold` | `0.4` | Minimum similarity score |

### LLM Settings (`core/bot.py`)

```python
response = await self.openai_client.responses.create(
    model=config.openai_model,
    input=messages,
    reasoning={"effort": "minimal"},  # Minimal "thinking" for speed
    text={"verbosity": "low"}         # Concise responses
)
```

---

## Local Development

### Testing Without Deployment

Use `test_bot.ipynb` to test the full RAG + LLM pipeline locally:

```python
# Initialize bot
bot = OnboardingBot()

# Test a question
await ask("How do I use the AI Background Remover?")

# Test retrieval only (no LLM cost)
test_retrieval("templates")
```

**Note:** The notebook imports need updating after the refactor:
```python
from src.core.config import config
from src.core.bot import OnboardingBot
```

### Running the Server Locally

```bash
# From project root
cd /workspaces/py/projects/onboarding_mascot

# Load environment
source ../../.env

# Run the server
python -m src.integrations.slack.app
```

### Exposing for Slack (Local Dev)

```bash
# Install ngrok: https://ngrok.com
ngrok http 8080

# Configure Slack webhook:
# https://api.slack.com/apps → Your App → Event Subscriptions
# Request URL: https://YOUR-NGROK-URL/slack/events
```

---

## Deployment

### Cloud Run Deployment

```bash
cd /workspaces/py/projects/onboarding_mascot
source ../../.env
./deploy.sh
```

The `deploy.sh` script:
1. Builds Docker image
2. Pushes to Google Artifact Registry
3. Deploys to Cloud Run
4. Configures environment variables

### Required GCP Setup

1. **Firestore** — Create database in Native mode (for conversation history)
2. **BigQuery** — Create table `prod_el.onboarding_mascot_metrics` with schema for logging
3. **Cloud Run** — Service account needs:
   - `Cloud Datastore User` (Firestore)
   - `BigQuery Data Editor` (logging)

---

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/slack/events` | POST | Slack webhook receiver |
| `/health` | GET | Health check for load balancers |
| `/` | GET | Service info |
| `/docs` | GET | Auto-generated API documentation |

---

## Monitoring & Debugging

### Logs

Key log messages to watch:
```
✅ Retrieved 5 chunks in 45.2ms          # RAG retrieval
📊 Token usage: input=2775, output=200    # LLM costs
✅ Response sent successfully             # Slack delivery
💾 Saved 2 messages to C123_1700000001    # Firestore write
```

### BigQuery Analytics

Query interaction data:
```sql
SELECT
  timestamp,
  user_question,
  bot_response,
  total_latency_ms,
  retrieval_time_ms,
  llm_generation_ms,
  responses_input_tokens,
  responses_cached_tokens,
  responses_output_tokens,
  responses_reasoning_tokens
FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics`
ORDER BY timestamp DESC
LIMIT 100
```

**All logged columns:**

| Column | Description |
|--------|-------------|
| `timestamp` | When the query happened |
| `thread_ts` | Slack thread identifier |
| `user_question` | The user's message |
| `bot_response` | The bot's reply |
| `total_latency_ms` | End-to-end response time |
| `retrieval_time_ms` | RAG retrieval time |
| `llm_generation_ms` | LLM generation time |
| `chunks_retrieved` | JSON array of retrieved docs with scores |
| `system_prompt_with_context` | Full prompt sent to LLM |
| `responses_input_tokens` | Total input tokens |
| `responses_cached_tokens` | Cached input tokens (cost savings) |
| `responses_output_tokens` | Output tokens |
| `responses_reasoning_tokens` | Reasoning tokens |
| `error` | Error message if failed |

### Common Issues

| Issue | Solution |
|-------|----------|
| Bot doesn't respond | Check Slack webhook URL, bot scopes, channel membership |
| "Collection not found" | Trigger Dagster assets to populate Weaviate collections |
| Slow responses | Check `reasoning.effort` and `text.verbosity` settings |
| Missing context in follow-ups | Verify Firestore is connected |

---

## Adding a New Integration

The `core/` module is platform-agnostic. To add Discord, Web API, etc.:

1. Create `src/integrations/discord/`
2. Import `OnboardingBot` from `core.bot`
3. Import `FirestoreConversationStore` from `core.storage`
4. Implement platform-specific event handlers
5. The RAG and LLM logic remain unchanged

---

## Quick Reference

### Run Locally
```bash
python -m src.integrations.slack.app
```

### Deploy
```bash
./deploy.sh
```

### Test in Notebook
```python
await ask("How do I use mockups?")
```

### Update Documentation (Weaviate)
Access Dagster UI and trigger the documentation upload assets:
- MascotHelpArticles asset (for documentation updates)
- MascotQAPairs asset (for Q&A pairs updates)

