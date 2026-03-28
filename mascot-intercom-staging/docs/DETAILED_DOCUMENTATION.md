# 🤖 Onboarding Mascot - Complete Technical Handover Documentation

**Last Updated:** January 2026
**Owner:** Syed (Departing)
**Status:** Production
**Platform:** Google Cloud Run
**Integration:** Slack

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Quick Start Guide](#quick-start-guide)
4. [Core Components Deep Dive](#core-components-deep-dive)
5. [RAG System Explained](#rag-system-explained)
6. [Deployment Guide](#deployment-guide)
7. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
8. [Integration Architecture](#integration-architecture)
9. [Moving to Other Platforms](#moving-to-other-platforms)
10. [Data Management](#data-management)
11. [BigQuery Logging & Metrics](#bigquery-logging--metrics)
12. [Configuration Reference](#configuration-reference)
13. [Python Files Reference](#python-files-reference)

---

## 🎯 Executive Summary

### What It Does

The Onboarding Mascot is an AI-powered Slack bot that helps Kittl users learn about design tools through natural conversation. It uses **Retrieval Augmented Generation (RAG)** to provide accurate, documentation-grounded responses.

**Example Interaction:**
```
User: "How do I remove a background from an image?"

Bot: "You can use the AI Background Remover! Here's how:
     1. Select your image on the canvas
     2. Click 'Remove Background' in the properties panel
     3. The clipped image saves to your Clipped Images folder
     Watch the video: [link]"
```

### Key Capabilities

- ✅ **Natural language understanding** of user questions
- ✅ **RAG-powered responses** grounded in documentation
- ✅ **Conversation memory** for follow-up questions
- ✅ **Dual-collection retrieval** (docs + Q&A pairs)
- ✅ **Platform-agnostic core** (easy to add new integrations)
- ✅ **Comprehensive logging** to BigQuery

### Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **LLM** | OpenAI GPT-5-mini (Responses API) | Generate responses |
| **Vector DB** | Weaviate Cloud | Store & search documentation |
| **Conversation Storage** | Google Firestore | Thread memory across instances |
| **Data Warehouse** | Google BigQuery | Metrics & logging |
| **Chat Platform** | Slack (Bolt SDK) | User interface |
| **Web Framework** | FastAPI + Uvicorn | HTTP server |
| **Deployment** | Google Cloud Run | Containerized hosting |

---

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          USER (Slack)                           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ @mention or DM
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              Google Cloud Run (FastAPI + Slack Bolt)            │
│                  integrations/slack/app.py                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
         ┌────────────────────────────────────────┐
         │       core/bot.py (OnboardingBot)      │
         │  - Orchestrates RAG + LLM              │
         │  - Manages conversation context        │
         └────────┬───────────────────────────────┘
                  │
                  │ delegates to
                  ▼
         ┌────────────────────────────────────────┐
         │    rag/retriever.py (RAG System)       │
         │  - Dual-collection search              │
         │  - Hybrid search (semantic + keyword)  │
         └────┬─────────────────┬─────────────────┘
              │                 │
    ┌─────────┴─────────┐      └─────────────────┐
    │                   │                        │
    ▼                   ▼                        ▼
┌──────────┐    ┌──────────────┐      ┌─────────────────┐
│ Weaviate │    │  Firestore   │      │    BigQuery     │
│  (RAG)   │    │ (Conv Hist)  │      │   (Logging)     │
└──────────┘    └──────────────┘      └─────────────────┘
     │
     │ retrieves
     ▼
┌──────────────────────┐
│ - MascotHelpArticles     │
│ - MascotQAPairs    │
└──────────────────────┘
```

### Request Flow (Step-by-Step)

1. **Slack Event Received**
   - User mentions bot or sends DM
   - Slack sends event to `/slack/events` endpoint

2. **Event Processing** (`integrations/slack/app.py`)
   - Validate Slack signature
   - Deduplicate event (check in-memory cache)
   - Extract user question, thread context
   - Remove bot mention from text

3. **Context Retrieval** (`core/storage.py`)
   - Load previous conversation from Firestore
   - Thread key: `{channel_id}_{thread_ts}`
   - Get last Q&A pair for follow-ups

4. **Bot Processing** (`core/bot.py`)
   - Initialize `OnboardingBot` with context
   - Build prompt with previous conversation

5. **RAG Retrieval** (`rag/retriever.py`)
   - **Stage 1:** Query `MascotHelpArticles` collection
   - **Stage 2:** Query `MascotQAPairs` collection
   - Combine results, sort by similarity
   - Return top 5 chunks

6. **LLM Generation** (`core/bot.py`)
   - Build system prompt with:
     - Base personality from `system_prompt.txt`
     - Retrieved documentation chunks
     - Previous conversation context
   - Call OpenAI Responses API
   - Extract response + token metrics

7. **Response Handling** (`integrations/slack/handlers.py`)
   - Format for Slack markdown
   - Handle 4000 character limit
   - Send to Slack thread
   - Save conversation to Firestore
   - Log metrics to BigQuery

---

## 🚀 Quick Start Guide

### Prerequisites

1. **Install gcloud CLI**: https://cloud.google.com/sdk/install
2. **Authenticate**: `gcloud auth login`
3. **Set project**: `gcloud config set project kittl-data-platform`
4. **Install Docker**: https://docs.docker.com/get-docker/

### Local Development Setup

```bash
# 1. Navigate to project
cd /workspaces/py/projects/onboarding_mascot

# 2. Load environment variables
source ../../.env

# 3. Run the server
python -m src.integrations.slack.app

# Server starts at http://0.0.0.0:8080
```

### Testing Without Slack

Use `test_bot.ipynb` for local testing:

```python
# Initialize bot
from src.core.bot import OnboardingBot
bot = OnboardingBot()

# Test a question
response = await bot.process_message(
    message="How do I use the AI Background Remover?",
    rag_result=retriever.retrieve("How do I use the AI Background Remover?")
)

print(response)
```

### Deploying to Production

```bash
# 1. Ensure .env is configured
cd /workspaces/py/projects/onboarding_mascot

# 2. Load environment
source ../../.env

# 3. Deploy
./deploy.sh

# 4. Update Slack webhook URL
# Go to: https://api.slack.com/apps → Your App → Event Subscriptions
# Set Request URL to: <Cloud Run URL>/slack/events
```

---

## 🔍 Core Components Deep Dive

### 1. OnboardingBot (`core/bot.py`)

**Purpose:** Main orchestrator that coordinates RAG retrieval and LLM generation.

**Key Responsibilities:**
- Initialize RAG retriever
- Load system prompt
- Build enhanced prompts with context
- Call OpenAI Responses API
- Extract token usage metrics

**Important Methods:**

```python
class OnboardingBot:
    def __init__(self):
        # Initialize Weaviate retriever
        self.retriever = WeaviateRetriever(...)

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        # Initialize OpenAI client
        self.openai_client = AsyncOpenAI(...)

    async def process_message(
        self,
        message: str,
        rag_result: RAGResult,
        previous_context: Optional[Dict] = None
    ) -> tuple[str, str, int, int, int, int]:
        """
        Process user message with RAG + LLM

        Returns:
            (response_text, system_prompt, input_tokens,
             output_tokens, cached_tokens, reasoning_tokens)
        """
```

**Configuration:**
- Model: `gpt-5-mini` (configurable in `config.py`)
- Reasoning effort: `low` (for quality)
- Verbosity: `medium` (for detail)

### 2. RAG Retriever (`rag/retriever.py`)

**Purpose:** Retrieve relevant documentation from Weaviate using hybrid search.

**Dual-Collection Strategy:**

The bot queries **TWO collections simultaneously**:

1. **MascotHelpArticles** - Chunked documentation from .docx files
2. **MascotQAPairs** - Previously answered support tickets

**Why Two Collections?**
- Documentation covers "how to use" features
- Q&A pairs cover common user problems/edge cases
- Both compete for top-K slots based on relevance

**Hybrid Search Configuration:**
```python
# 80% semantic similarity, 20% keyword matching
alpha = 0.8

# Minimum similarity score to include
similarity_threshold = 0.4

# Number of chunks to return
top_k = 5
```

### 3. Conversation Storage (`core/storage.py`)

**Purpose:** Persist conversation history in Firestore for follow-up questions.

**Why Firestore?**
- Cloud Run can scale to multiple instances
- Instances can restart anytime
- Firestore provides shared, persistent state
- Enables multi-turn conversations

**Storage Structure:**
```python
# Document ID: "{channel_id}_{thread_ts}"
{
  "created_at": "2026-01-20T...",
  "updated_at": "2026-01-20T...",
  "messages": [
    {"role": "user", "content": "How do I use templates?"},
    {"role": "assistant", "content": "Here's how to use templates..."},
    {"role": "user", "content": "Can I edit them?"},  # Follow-up
    {"role": "assistant", "content": "Yes! You can edit..."}
  ]
}
```

**Follow-Up Question Handling:**

When user asks a follow-up like "Can I edit them?", the bot:
1. Retrieves last Q&A pair from Firestore
2. Includes it in system prompt as context
3. LLM understands "them" = templates
4. Provides relevant answer

### 4. System Prompt (`config/system_prompt.txt`)

**Purpose:** Define bot's personality, behavior, and response guidelines.

**Key Sections:**

**Response Guidelines:**
```
*Critical Rules:*
- DO NOT make up information - stick to documentation
- Be succinct - get to the point quickly
- DO NOT suggest follow-up topics
- DO use simple closings like "Let me know if you need help!"
```

**Handling Missing Information:**

**Scenario 1: Generic Questions** ("I'm confused", "What can Kittl do?")
- Use "Summary of Kittl" section
- Encourage specific follow-ups

**Scenario 2: Specific Features Not in Docs** ("Can I export to .AI format?")
- Acknowledge you don't have confirmation
- Direct to support ONLY
- DO NOT suggest workarounds

**Formatting Rules:**
```
CRITICAL: Slack does NOT use standard Markdown
- For bold: Use *single asterisks* (NOT **double**)
- For italics: Use _underscores_
- For code: Use `backticks`
- For headings: Use *bold text* on its own line (NO ### symbols)
```

**Guardrails:**

1. **Pricing/Account Questions** → Direct to pricing page + support
2. **Deleted Projects** → Reassure + direct to support
3. **Competitor Comparisons** → Direct to support
4. **Design Review** → Cannot view/create designs

**Critical Facts (Always Prioritize):**
- AI Upscaler is FREE for Expert Plan users
- Token balance: click *star icon* in *lower-right* corner
- AI Tokens = AI Credits (same thing)
- Pro Plan users: purchase from website, NOT editor

---

## 🧠 RAG System Explained

### What is RAG?

**Retrieval Augmented Generation (RAG)** is a technique that combines:
1. **Retrieval:** Finding relevant documents from a knowledge base
2. **Augmentation:** Adding those documents to the LLM prompt
3. **Generation:** LLM generates response based on retrieved context

**Why RAG?**
- ✅ Reduces hallucinations (LLM uses real docs)
- ✅ Keeps responses up-to-date (update docs, not model)
- ✅ Provides source attribution (shows which docs used)
- ✅ More cost-effective than fine-tuning

### Dual-Collection Strategy

The Onboarding Mascot uses **two separate Weaviate collections**:

#### Collection 1: MascotHelpArticles

**Purpose:** Store chunked documentation from .docx files

**Source:** Google Drive → Onboarding Docs folder

**Structure:**
```python
{
  "tool": "Templates Tool",
  "section": "How to Use",
  "content": "To browse templates, click the Templates icon...",
  "video_url": "https://cdnp.kittl.com/...",
  "created_at": "2026-01-20T..."
}
```

**Chunking Strategy:**
- Each tool has multiple sections:
  - Tool Description
  - How to Use
  - Key Features
  - Tips & Tricks
- Each section = one chunk
- Preserves context within sections

**Upload Process:**
1. Download .docx files from Google Drive (OAuth)
2. Parse with python-docx
3. Split by section headers
4. Upload to Weaviate with OpenAI embeddings

#### Collection 2: MascotQAPairs

**Purpose:** Store previously answered support tickets

**Source:** Intercom customer support data

**Structure:**
```python
{
  "qa_pair": "Q: How do I cancel my subscription?\nA: To cancel...",
  "topic": "Billing",
  "created_at": "2026-01-20T..."
}
```

**Why Include Q&A Pairs?**
- Covers edge cases not in docs
- Real user language patterns
- Common problems/workarounds
- Complements documentation

### Hybrid Search Explained

**Hybrid search** combines two search methods:

1. **Semantic Search (80%)** - Meaning-based
   - "How do I remove backgrounds?" matches "AI Background Remover"
   - Uses OpenAI embeddings (vector similarity)

2. **Keyword Search (20%)** - Exact term matching
   - "AI Upscaler" matches "AI Upscaler" exactly
   - Uses BM25 algorithm

**Configuration:**
```python
alpha = 0.8  # 80% semantic, 20% keyword

# Why 80/20?
# - Semantic: Catches conceptual matches
# - Keyword: Ensures exact terms aren't missed
# - Balance: Best of both worlds
```

**Example:**

Query: "How do I make images bigger?"

**Semantic matches (80%):**
- "AI Image Upscaler" (0.85 similarity)
- "Increase resolution" (0.78 similarity)

**Keyword matches (20%):**
- "bigger images" (exact phrase)
- "enlarge" (synonym)

**Combined score:** Weighted average → Top results

### What Query Text is Used in RAG?

**IMPORTANT:** The RAG system uses the **raw user message** for retrieval, NOT an enhanced or modified version.

**Query Flow:**

```
User types in Slack: "@bot How do I use templates?"
    ↓
Remove @mention: "How do I use templates?"
    ↓
THIS EXACT TEXT is used for RAG retrieval
    ↓
Query MascotHelpArticles with: "How do I use templates?"
Query MascotQAPairs with: "How do I use templates?"
    ↓
Retrieved chunks are added to system prompt
    ↓
LLM sees: system prompt + retrieved docs + user message
```

**Why Raw Message?**
- User's natural language is best for semantic search
- No risk of query expansion introducing noise
- Simpler, more predictable behavior
- Embeddings trained on natural questions

**For Follow-Up Questions:**

When user asks a follow-up, the RAG system STILL uses only the current message:

```
Previous conversation:
User: "How do I use templates?"
Bot: "To use templates, click..."

User asks: "Can I edit them?"
    ↓
RAG queries with: "Can I edit them?"  ← Just this!
    ↓
Retrieved chunks may not have "template" context
    ↓
BUT: Previous conversation is added to system prompt
    ↓
LLM sees:
  - System prompt
  - Retrieved docs (about "editing")
  - Previous Q&A (mentions "templates")
  - Current question ("Can I edit them?")
    ↓
LLM infers "them" = templates from conversation history
```

**This means:**
- RAG retrieval is **context-independent** (only current message)
- LLM inference is **context-aware** (sees conversation history)
- Follow-up questions may retrieve less relevant docs
- But LLM can still answer correctly using conversation context

**Alternative Approach (Not Currently Implemented):**

Some RAG systems use "query expansion" for follow-ups:

```python
# NOT USED - but could improve follow-up retrieval
def expand_query(current_question, previous_context):
    """
    Expand follow-up questions with context

    Example:
      Current: "Can I edit them?"
      Previous: "How do I use templates?"
      Expanded: "Can I edit templates?"
    """
    if previous_context:
        return f"{previous_context['topic']} {current_question}"
    return current_question
```

**If you want to implement this:**
1. Modify `rag/retriever.py` to accept `previous_context`
2. Expand query before searching Weaviate
3. Test that it improves follow-up accuracy
4. Monitor for false positives (over-expansion)

### Retrieval Process Flow

**Example Query:** "How do I use templates?"

```
User Query: "How do I use templates?"
    ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 1: Query MascotHelpArticles Collection                     │
│                                                              │
│ Configuration:                                               │
│   - RAG_TOP_K = 5 (desired final chunks)                    │
│   - Candidate limit = RAG_TOP_K * 2 = 10                    │
│   - Hybrid search: alpha=0.8 (80% semantic, 20% keyword)    │
│   - Similarity threshold = 0.4                               │
│   - Query text: "How do I use templates?" (raw, unmodified) │
│                                                              │
│ Process:                                                     │
│   1. Weaviate performs hybrid search                        │
│   2. Returns up to 20 results (limit * 2 for safety)        │
│   3. Filter: Keep only chunks with similarity ≥ 0.4         │
│                                                              │
│ Example Result: 8 chunks pass the threshold                 │
│   - Chunk 1: "Templates Tool: How to Use" (similarity: 0.87)│
│   - Chunk 2: "Templates Tool: Description" (similarity: 0.82)│
│   - Chunk 3: "Templates Tool: Tips" (similarity: 0.76)      │
│   - Chunk 4: "Gallery: Using Templates" (similarity: 0.71)  │
│   - Chunk 5: "Projects: Template Basics" (similarity: 0.68) │
│   - Chunk 6: "Templates Tool: Features" (similarity: 0.55)  │
│   - Chunk 7: "Editor: Template Mode" (similarity: 0.48)     │
│   - Chunk 8: "Workspace: Templates" (similarity: 0.42)      │
└──────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 2: Query MascotQAPairs Collection                    │
│                                                              │
│ Configuration:                                               │
│   - Same settings as Step 1                                  │
│   - Candidate limit = 10                                     │
│   - Query text: "How do I use templates?" (unchanged)        │
│                                                              │
│ Process:                                                     │
│   1. Weaviate performs hybrid search on Q&A pairs           │
│   2. Returns up to 20 results                                │
│   3. Filter: Keep only chunks with similarity ≥ 0.4         │
│                                                              │
│ Example Result: 3 chunks pass the threshold                 │
│   - Chunk 1: "Q: How to use templates? A: ..." (0.79)       │
│   - Chunk 2: "Q: Can I customize templates? A: ..." (0.64)  │
│   - Chunk 3: "Q: Where are templates stored? A: ..." (0.51) │
└──────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 3: Combine & Sort All Candidates                       │
│                                                              │
│ Process:                                                     │
│   1. Merge results from both collections                     │
│      - MascotHelpArticles: 8 chunks                              │
│      - MascotQAPairs: 3 chunks                             │
│      - Total candidates: 11 chunks                           │
│                                                              │
│   2. Sort ALL chunks by similarity score (descending)        │
│      - Rank 1: 0.87 (MascotHelpArticles)                         │
│      - Rank 2: 0.82 (MascotHelpArticles)                         │
│      - Rank 3: 0.79 (MascotQAPairs) ← Q&A beats some docs │
│      - Rank 4: 0.76 (MascotHelpArticles)                         │
│      - Rank 5: 0.71 (MascotHelpArticles)                         │
│      - Rank 6: 0.68 (MascotHelpArticles)                         │
│      - Rank 7: 0.64 (MascotQAPairs)                        │
│      - Rank 8: 0.55 (MascotHelpArticles)                         │
│      - Rank 9: 0.51 (MascotQAPairs)                        │
│      - Rank 10: 0.48 (MascotHelpArticles)                        │
│      - Rank 11: 0.42 (MascotHelpArticles)                        │
│                                                              │
│   3. Select top RAG_TOP_K chunks (top 5)                     │
│      - Final selection: Ranks 1-5                            │
│      - Mix of 4 docs + 1 Q&A pair                            │
│                                                              │
│   4. Assign final ranks to selected chunks                   │
│      - Chunk 1: rank=1, similarity=0.87, source="docs"       │
│      - Chunk 2: rank=2, similarity=0.82, source="docs"       │
│      - Chunk 3: rank=3, similarity=0.79, source="qa"         │
│      - Chunk 4: rank=4, similarity=0.76, source="docs"       │
│      - Chunk 5: rank=5, similarity=0.71, source="docs"       │
└──────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 4: Format for LLM System Prompt                        │
│                                                              │
│ Process:                                                     │
│   1. Build context string from top 5 chunks                  │
│   2. Format each chunk as:                                   │
│      --- [tool]: [section] ---                               │
│      [content]                                               │
│                                                              │
│   3. Inject into system prompt                               │
│   4. Add conversation history (if follow-up)                 │
│   5. Send to OpenAI Responses API                            │
│                                                              │
│ Result: LLM receives comprehensive, ranked context           │
└──────────────────────────────────────────────────────────────┘
```

**Key Numbers to Remember:**

| Metric | Value | Explanation |
|--------|-------|-------------|
| **Candidate Limit per Collection** | 10 | `RAG_TOP_K * 2` to ensure enough options |
| **Total Candidates Requested** | 20 | 10 from each collection |
| **Weaviate Returns** | Up to 40 | `limit * 2` for safety margin |
| **After Threshold Filter** | Variable | Only chunks with similarity ≥ 0.4 |
| **Final Chunks Sent to LLM** | 5 | `RAG_TOP_K` - the best from both collections |

**Why This Matters:**

- **Dual-collection ensures diversity**: Both documentation and real Q&A compete fairly
- **Threshold filtering ensures quality**: No irrelevant chunks (< 0.4 similarity)
- **Top-K selection ensures relevance**: Only the best chunks make it to the LLM
- **Collections compete on merit**: A highly relevant Q&A can beat lower-scoring docs

### Context Building

**Retrieved chunks are formatted like this:**

```markdown
Here is relevant documentation to help answer the user's question:

--- Templates Tool: Tool Description ---
Templates are pre-made designs that you can customize...

--- Templates Tool: How to Use ---
To browse templates:
1. Click the Templates icon in the left panel
2. Browse by category or search
3. Click a template to add it to your canvas

--- Customer Support: Q&A ---
Q: Can I edit templates after adding them?
A: Yes! Templates are fully editable once added to your canvas...
```

This context is injected into the system prompt before the LLM sees it.

### Similarity Threshold

**Purpose:** Filter out irrelevant chunks

```python
similarity_threshold = 0.4  # 0.0 - 1.0

# Scores:
# 0.9-1.0: Highly relevant
# 0.7-0.9: Relevant
# 0.4-0.7: Somewhat relevant
# 0.0-0.4: Not relevant (filtered out)
```

**Why 0.4?**
- Too high (0.7): Misses useful context
- Too low (0.2): Includes noise
- 0.4: Good balance for general queries

**Tuning:**
- Increase (0.5-0.6): For precise queries
- Decrease (0.3): For broad queries

---

## 📊 BigQuery Logging & Metrics

### Overview

**Every interaction** with the bot is logged to BigQuery for monitoring, debugging, and analytics. This is critical for understanding bot performance, costs, and user behavior.

**Table:** `kittl-data-platform.prod_el.onboarding_mascot_metrics`

### Table Schema

```sql
CREATE TABLE `kittl-data-platform.prod_el.onboarding_mascot_metrics` (
  -- Identification
  timestamp TIMESTAMP,                    -- When the interaction occurred
  thread_ts STRING,                       -- Slack thread ID (for tracking conversations)

  -- User Interaction
  user_question STRING,                   -- The exact question the user asked
  bot_response STRING,                    -- The bot's complete response

  -- Performance Metrics
  total_latency_ms FLOAT64,              -- Total time from question to response
  retrieval_time_ms FLOAT64,             -- Time spent querying Weaviate
  llm_generation_ms FLOAT64,             -- Time spent waiting for OpenAI

  -- RAG Context
  chunks_retrieved JSON,                  -- Array of chunks used (with similarity scores)
  system_prompt_with_context STRING,      -- Complete prompt sent to LLM (includes docs)

  -- Token Usage (OpenAI Responses API)
  responses_input_tokens INT64,          -- Tokens in the prompt (system + user message)
  responses_cached_tokens INT64,         -- Tokens retrieved from cache (cheaper!)
  responses_output_tokens INT64,         -- Tokens in the bot's response
  responses_reasoning_tokens INT64,      -- Tokens used for reasoning (gpt-5-mini feature)

  -- Legacy Token Fields (deprecated but kept for compatibility)
  system_prompt_tokens INT64,            -- Old field (use responses_input_tokens)
  output_tokens INT64,                   -- Old field (use responses_output_tokens)

  -- Error Tracking
  error STRING                           -- Error message if something went wrong
);
```

### What Each Field Means

#### Identification Fields

| Field | Example | Purpose |
|-------|---------|---------|
| `timestamp` | `2026-01-23 14:30:45 UTC` | When the interaction happened |
| `thread_ts` | `C07172ECUP3_1234567890.123456` | Unique thread identifier (channel_id + timestamp) |

#### Interaction Fields

| Field | Example | Purpose |
|-------|---------|---------|
| `user_question` | `"How do I use templates?"` | Exact user input (after removing @mention) |
| `bot_response` | `"To use templates, click..."` | Complete bot response sent to Slack |

#### Performance Fields

| Field | Typical Value | What It Means |
|-------|---------------|---------------|
| `total_latency_ms` | `3500-5000ms` | Total time from receiving question to sending response |
| `retrieval_time_ms` | `50-150ms` | Time to query Weaviate and retrieve docs |
| `llm_generation_ms` | `2000-4000ms` | Time waiting for OpenAI to generate response |

**Performance Breakdown:**
- **Retrieval (2-3%):** Fast vector search in Weaviate
- **LLM Generation (70-80%):** Most time spent here (OpenAI API call)
- **Overhead (15-25%):** Firestore, formatting, logging

#### RAG Context Fields

**`chunks_retrieved` (JSON):**
```json
[
  {
    "tool": "Templates Tool",
    "section": "How to Use",
    "content": "To browse templates, click...",
    "similarity": 0.87,
    "rank": 1,
    "source": "docs"
  },
  {
    "tool": "Customer Support",
    "section": "Q&A",
    "content": "Q: Can I edit templates?\nA: Yes!...",
    "similarity": 0.76,
    "rank": 2,
    "source": "qa"
  }
]
```

**Why This Matters:**
- See which docs the bot used to answer
- Verify retrieval quality (similarity scores)
- Debug incorrect answers (wrong docs retrieved?)
- Identify gaps in documentation

**`system_prompt_with_context` (STRING):**

This is the **complete prompt** sent to the LLM, including:
1. Base system prompt (personality, guidelines)
2. Retrieved documentation chunks
3. Previous conversation context (for follow-ups)

**Example (truncated):**
```
You are Kittl's friendly onboarding assistant...

Here is relevant documentation:
--- Templates Tool: How to Use ---
To browse templates, click...

Previous conversation:
User: "How do I use templates?"
Assistant: "To use templates..."

Current user question: "Can I edit them?"
```

**Why This Matters:**
- Debug why bot gave a certain answer
- Verify RAG context was included correctly
- Check if conversation history was used
- Audit for prompt injection attempts

#### Token Usage Fields

**Understanding OpenAI Responses API Tokens:**

| Field | What It Counts | Cost Impact |
|-------|----------------|-------------|
| `responses_input_tokens` | System prompt + user message + retrieved docs | Medium cost |
| `responses_cached_tokens` | Portions of input that were cached (reused) | **75% cheaper!** |
| `responses_output_tokens` | Bot's response text | High cost (4x input) |
| `responses_reasoning_tokens` | Internal reasoning (gpt-5-mini feature) | Medium cost |

**Example:**
```
responses_input_tokens: 2850
  ├─ System prompt: ~500 tokens
  ├─ Retrieved docs: ~2000 tokens
  └─ User message: ~350 tokens

responses_cached_tokens: 1200
  └─ System prompt + docs (cached from previous request)

responses_output_tokens: 180
  └─ Bot's response

responses_reasoning_tokens: 450
  └─ Internal reasoning (not shown to user)
```

**Cost Calculation (GPT-5-mini example):**
```
Input cost:  (2850 - 1200) * $0.00000015 = $0.000248
Cached cost: 1200 * $0.000000037 = $0.000044  (75% cheaper!)
Output cost: 180 * $0.00000060 = $0.000108
Reasoning:   450 * $0.00000015 = $0.000068
────────────────────────────────────────────
Total:                           $0.000468 per request
```

**Why Caching Matters:**
- System prompt is usually the same → cached
- Documentation chunks often repeat → cached
- Can reduce costs by 30-50%!

### Useful Queries

**1. Daily Usage & Costs**
```sql
SELECT
  DATE(timestamp) AS date,
  COUNT(*) AS total_requests,
  AVG(total_latency_ms) AS avg_latency_ms,

  -- Token breakdown
  SUM(responses_input_tokens) AS total_input_tokens,
  SUM(responses_cached_tokens) AS total_cached_tokens,
  SUM(responses_output_tokens) AS total_output_tokens,

  -- Cost estimation (GPT-5-mini pricing)
  ROUND(
    SUM(responses_input_tokens - IFNULL(responses_cached_tokens, 0)) * 0.00000015 +
    SUM(IFNULL(responses_cached_tokens, 0)) * 0.000000037 +
    SUM(responses_output_tokens) * 0.00000060 +
    SUM(IFNULL(responses_reasoning_tokens, 0)) * 0.00000015,
    4
  ) AS estimated_cost_usd

FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics`
WHERE DATE(timestamp) >= CURRENT_DATE() - 30
  AND error IS NULL
GROUP BY date
ORDER BY date DESC;
```

**2. Most Common Questions**
```sql
SELECT
  user_question,
  COUNT(*) AS frequency,
  AVG(total_latency_ms) AS avg_latency_ms,
  AVG(ARRAY_LENGTH(JSON_EXTRACT_ARRAY(chunks_retrieved))) AS avg_chunks_used
FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics`
WHERE DATE(timestamp) >= CURRENT_DATE() - 7
  AND error IS NULL
GROUP BY user_question
ORDER BY frequency DESC
LIMIT 20;
```

**3. Retrieval Quality Analysis**
```sql
WITH chunk_data AS (
  SELECT
    user_question,
    JSON_EXTRACT_SCALAR(chunk, '$.tool') AS tool,
    JSON_EXTRACT_SCALAR(chunk, '$.section') AS section,
    CAST(JSON_EXTRACT_SCALAR(chunk, '$.similarity') AS FLOAT64) AS similarity,
    JSON_EXTRACT_SCALAR(chunk, '$.source') AS source
  FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics`,
  UNNEST(JSON_EXTRACT_ARRAY(chunks_retrieved)) AS chunk
  WHERE DATE(timestamp) >= CURRENT_DATE() - 7
    AND error IS NULL
)
SELECT
  tool,
  source,
  COUNT(*) AS times_retrieved,
  AVG(similarity) AS avg_similarity,
  MIN(similarity) AS min_similarity,
  MAX(similarity) AS max_similarity
FROM chunk_data
GROUP BY tool, source
ORDER BY times_retrieved DESC;
```

**4. Performance Breakdown**
```sql
SELECT
  DATE(timestamp) AS date,
  AVG(retrieval_time_ms) AS avg_retrieval_ms,
  AVG(llm_generation_ms) AS avg_llm_ms,
  AVG(total_latency_ms) AS avg_total_ms,

  -- Percentage breakdown
  ROUND(AVG(retrieval_time_ms) / AVG(total_latency_ms) * 100, 1) AS retrieval_pct,
  ROUND(AVG(llm_generation_ms) / AVG(total_latency_ms) * 100, 1) AS llm_pct

FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics`
WHERE DATE(timestamp) >= CURRENT_DATE() - 7
  AND error IS NULL
GROUP BY date
ORDER BY date DESC;
```

**5. Error Analysis**
```sql
SELECT
  DATE(timestamp) AS date,
  error,
  COUNT(*) AS error_count,
  ARRAY_AGG(user_question LIMIT 3) AS sample_questions
FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics`
WHERE error IS NOT NULL
  AND DATE(timestamp) >= CURRENT_DATE() - 7
GROUP BY date, error
ORDER BY date DESC, error_count DESC;
```

**6. Cache Effectiveness**
```sql
SELECT
  DATE(timestamp) AS date,
  AVG(responses_cached_tokens / NULLIF(responses_input_tokens, 0) * 100) AS cache_hit_rate_pct,
  SUM(responses_cached_tokens) AS total_cached_tokens,
  SUM(responses_input_tokens) AS total_input_tokens,

  -- Cost savings from caching
  ROUND(
    SUM(responses_cached_tokens) * (0.00000015 - 0.000000037),
    4
  ) AS cache_savings_usd

FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics`
WHERE DATE(timestamp) >= CURRENT_DATE() - 30
  AND error IS NULL
GROUP BY date
ORDER BY date DESC;
```

### Accessing the Data

**BigQuery Console:**
```
https://console.cloud.google.com/bigquery?project=kittl-data-platform
→ Navigate to: prod_el.onboarding_mascot_metrics
```

**Command Line:**
```bash
# Export to CSV
bq extract \
  --destination_format=CSV \
  kittl-data-platform:prod_el.onboarding_mascot_metrics \
  gs://your-bucket/metrics.csv

# Query from terminal
bq query --use_legacy_sql=false \
  'SELECT * FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics` LIMIT 10'
```

---

## 🚀 Deployment Guide

### Prerequisites

**Required Tools:**
- gcloud CLI (authenticated)
- Docker (with buildx)
- Access to kittl-data-platform GCP project

**Required Permissions:**
- Cloud Run Admin
- Artifact Registry Writer
- Service Account User

### Environment Variables

**Required in `.env` file:**

```bash
# Slack
ONBOARDING_SLACK_BOT_TOKEN=xoxb-...
ONBOARDING_SLACK_SIGNING_SECRET=...

# OpenAI
OPENAI_API_KEY_DATA_BOT=sk-...

# Weaviate
WEAVIATE_URL=cluster-url.weaviate.cloud
WEAVIATE_API_KEY=...
WEAVIATE_COLLECTION=MascotHelpArticles

# RAG Settings (optional)
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.4

# GCP
GOOGLE_CLOUD_PROJECT=kittl-data-platform

# Optional
DEBUG=false
ENVIRONMENT=production
```

### Deployment Steps

**1. Prepare Environment**
```bash
cd /workspaces/py/projects/onboarding_mascot
source ../../.env
```

**2. Run Deployment Script**
```bash
./deploy.sh
```

**What the script does:**
1. ✅ Validates environment variables
2. ✅ Configures Artifact Registry authentication
3. ✅ Builds Docker image (linux/amd64)
4. ✅ Pushes to Google Artifact Registry
5. ✅ Deploys to Cloud Run
6. ✅ Sets environment variables
7. ✅ Outputs service URL

**3. Manually Switch to Latest Revision (Required)**

⚠️ **Important:** After deployment, you must manually switch to the latest revision in the Cloud Run UI. The deployment script creates a new revision, but Cloud Run doesn't automatically route traffic to it.

**Steps:**
1. Go to [Cloud Run Console](https://console.cloud.google.com/run?project=kittl-data-platform)
2. Click on the `onboarding-assistant` service
3. Click on the **"Revisions"** tab (should be selected by default)
4. You'll see a list of revisions with traffic allocation percentages
5. Find the **newest revision** (top of the list, deployed most recently)
6. Click the **radio button** next to the newest revision to select it
7. Click the **"Manage traffic"** button (top right of the revisions table)
8. In the traffic management dialog:
   - Select the newest revision
   - Set traffic allocation to **100%**
   - Click **"Save"**
9. Verify the new revision shows **100%** traffic in the revisions table

**Why is this needed?**
Cloud Run creates a new revision on each deployment, but doesn't automatically route traffic to it. You must manually switch traffic allocation to activate the new code.

**4. Update Slack Webhook**

After deployment, you'll see:
```
Service URL: https://onboarding-assistant-xxx.run.app
Webhook URL: https://onboarding-assistant-xxx.run.app/slack/events
```

Go to: https://api.slack.com/apps → Your App → Event Subscriptions
Set Request URL to the webhook URL above

### Cloud Run Configuration

**Resource Allocation:**
```yaml
Memory: 512Mi
CPU: 1
Timeout: 300s (5 minutes)
Max Instances: 10
Min Instances: 1  # Always warm
Port: 8080
```

**Why min_instances=1?**
- Eliminates cold starts
- First user gets instant response
- Costs ~$10-15/month for always-on instance

**Environment Variables Set:**
```bash
ONBOARDING_SLACK_BOT_TOKEN
ONBOARDING_SLACK_SIGNING_SECRET
OPENAI_API_KEY_DATA_BOT
WEAVIATE_URL
WEAVIATE_API_KEY
WEAVIATE_COLLECTION
RAG_TOP_K
RAG_SIMILARITY_THRESHOLD
DEBUG
ENVIRONMENT
GOOGLE_CLOUD_PROJECT
```

### GCP Setup Requirements

**1. Firestore Database**
```bash
# Create Firestore database (Native mode)
gcloud firestore databases create --location=us-central1

# Collection: onboarding_conversations
# Created automatically by app
```

**2. BigQuery Table**
```sql
-- Already created (see BigQuery Logging section above)
-- Table: kittl-data-platform.prod_el.onboarding_mascot_metrics
```

**3. Service Account Permissions**

Cloud Run service account needs:
- `Cloud Datastore User` (Firestore access)
- `BigQuery Data Editor` (logging)

```bash
# Grant permissions
gcloud projects add-iam-policy-binding kittl-data-platform \
  --member="serviceAccount:SERVICE_ACCOUNT@kittl-data-platform.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding kittl-data-platform \
  --member="serviceAccount:SERVICE_ACCOUNT@kittl-data-platform.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
```

### Slack App Configuration

**Required OAuth Scopes:**
- `app_mentions:read` - Read @mentions
- `chat:write` - Send messages
- `im:history` - Read DM history
- `im:read` - Access DMs
- `im:write` - Send DMs

**Event Subscriptions:**
- `app_mention` - When bot is @mentioned
- `message.im` - Direct messages

**Request URL:**
```
https://onboarding-assistant-xxx.run.app/slack/events
```

Must show green checkmark ✅ for verification

### Viewing Logs

**Cloud Run Logs:**
```bash
# View recent logs
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=onboarding-assistant' \
  --limit=50 \
  --project=kittl-data-platform

# Stream logs (real-time)
gcloud beta run services logs tail onboarding-assistant \
  --region=us-central1 \
  --project=kittl-data-platform

# Filter for errors
gcloud logging read \
  'resource.labels.service_name=onboarding-assistant AND severity>=ERROR' \
  --limit=20 \
  --project=kittl-data-platform
```

**Key Log Messages:**
```
✅ Onboarding Bot initialized successfully
✅ Retrieved 5 chunks in 45.2ms
📊 Token usage: input=2775, output=200
✅ Response sent successfully
💾 Saved 2 messages to C123_1700000001
```

### Rollback Procedure

If deployment fails or has issues:

```bash
# 1. List revisions
gcloud run revisions list \
  --service=onboarding-assistant \
  --region=us-central1

# 2. Rollback to previous revision
gcloud run services update-traffic onboarding-assistant \
  --to-revisions=REVISION_NAME=100 \
  --region=us-central1
```

---

## 🔧 Monitoring & Troubleshooting

### Key Metrics to Watch

**1. Response Latency**
- **Target:** < 5 seconds
- **Components:**
  - RAG retrieval: ~50-100ms
  - LLM generation: 2-4 seconds
  - Total: 3-5 seconds

**2. Token Usage**
- **Input tokens:** 2000-3000 per request
- **Output tokens:** 150-300 per request
- **Cached tokens:** 1000-1500 (saves cost!)

**3. Retrieval Quality**
- **Chunks returned:** 5 (configurable)
- **Avg similarity:** > 0.6 (good quality)
- **Collections used:** Both MascotHelpArticles + MascotQAPairs

### Emergency Procedures

#### 🚨 CRITICAL: Bot Stops Responding

**Symptoms:**
- No acknowledgment in Slack when mentioned
- No response after waiting 30+ seconds
- Slack shows no typing indicator

**Immediate Actions (Do These First):**

**1. Check Cloud Run Service Status (2 minutes)**
```bash
# Check if service is running
gcloud run services describe onboarding-assistant \
  --region=us-central1 \
  --format="value(status.conditions.status)"

# Expected: "True"
# If "False": Service is down!
```

**If service is down:**
```bash
# Restart service (redeploy current version)
gcloud run services update onboarding-assistant \
  --region=us-central1 \
  --no-traffic  # Force new revision

# Then route traffic back
gcloud run services update-traffic onboarding-assistant \
  --to-latest \
  --region=us-central1
```

**2. Check Recent Logs for Errors (3 minutes)**
```bash
# Get last 20 error logs
gcloud logging read \
  'resource.labels.service_name=onboarding-assistant AND severity>=ERROR' \
  --limit=20 \
  --format=json

# Look for:
# - "Connection refused" → Weaviate/OpenAI down
# - "Permission denied" → Service account issue
# - "Timeout" → LLM taking too long
# - "Collection not found" → Weaviate issue
```

**3. Verify Slack Webhook (1 minute)**
```bash
# Get current Cloud Run URL
gcloud run services describe onboarding-assistant \
  --region=us-central1 \
  --format="value(status.url)"

# Go to: https://api.slack.com/apps
# → Your App → Event Subscriptions
# → Verify Request URL matches Cloud Run URL + /slack/events
# → Should show green checkmark ✅
```

**If webhook verification fails:**
- Cloud Run service might be rejecting requests
- Check service account permissions
- Check environment variables are set

**4. Test Health Endpoint (1 minute)**
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe onboarding-assistant \
  --region=us-central1 \
  --format="value(status.url)")

# Test health endpoint
curl -v $SERVICE_URL/health

# Expected: {"status": "healthy", "service": "onboarding-assistant"}
# If timeout or 500: Service has issues
```

**5. Check Service Account Permissions (2 minutes)**
```bash
# Get service account
SA=$(gcloud run services describe onboarding-assistant \
  --region=us-central1 \
  --format="value(spec.template.spec.serviceAccountName)")

# Check permissions
gcloud projects get-iam-policy kittl-data-platform \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:$SA"

# Must have:
# - roles/datastore.user (Firestore)
# - roles/bigquery.dataEditor (Logging)
```

**If permissions missing:**
```bash
# Add Firestore permission
gcloud projects add-iam-policy-binding kittl-data-platform \
  --member="serviceAccount:$SA" \
  --role="roles/datastore.user"

# Add BigQuery permission
gcloud projects add-iam-policy-binding kittl-data-platform \
  --member="serviceAccount:$SA" \
  --role="roles/bigquery.dataEditor"

# Restart service
gcloud run services update onboarding-assistant \
  --region=us-central1 \
  --no-traffic && \
gcloud run services update-traffic onboarding-assistant \
  --to-latest \
  --region=us-central1
```

**6. Check Environment Variables (2 minutes)**
```bash
# List all env vars
gcloud run services describe onboarding-assistant \
  --region=us-central1 \
  --format="yaml(spec.template.spec.containers[0].env)"

# Verify these exist:
# - ONBOARDING_SLACK_BOT_TOKEN
# - ONBOARDING_SLACK_SIGNING_SECRET
# - OPENAI_API_KEY_DATA_BOT
# - WEAVIATE_URL
# - WEAVIATE_API_KEY
# - GOOGLE_CLOUD_PROJECT
```

**If any missing:**
```bash
# Redeploy with correct env vars
cd /workspaces/py/projects/onboarding_mascot
source ../../.env
./deploy.sh
```

**7. Check External Dependencies (3 minutes)**

**Weaviate:**
```bash
# Test Weaviate connection
curl -H "Authorization: Bearer $WEAVIATE_API_KEY" \
  "$WEAVIATE_URL/v1/meta"

# Should return cluster info
# If timeout: Weaviate cluster down
# If 401: API key invalid
```

**OpenAI:**
```bash
# Test OpenAI API
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY_DATA_BOT"

# Should return model list
# If 401: API key invalid
# If timeout: OpenAI having issues
```

**8. Rollback to Previous Version (5 minutes)**

If recent deployment caused the issue:

```bash
# List recent revisions
gcloud run revisions list \
  --service=onboarding-assistant \
  --region=us-central1 \
  --limit=5

# Rollback to previous revision
gcloud run services update-traffic onboarding-assistant \
  --to-revisions=PREVIOUS_REVISION_NAME=100 \
  --region=us-central1

# Test bot in Slack
```

**Quick Rollback Decision Tree:**
```
Did bot work before recent deployment?
  YES → Rollback immediately (step 8)
  NO → Continue troubleshooting

Is this a new installation?
  YES → Check all setup steps (Firestore, BigQuery, Slack)
  NO → Check for infrastructure changes
```

#### 🚨 Bot Throws Errors in Responses

**Symptoms:**
- Bot responds but message contains error text
- Slack shows error message instead of answer
- Partial responses or truncated messages

**Diagnosis Steps:**

**1. Check BigQuery Error Logs (2 minutes)**
```sql
SELECT
  timestamp,
  user_question,
  error,
  bot_response
FROM `kittl-data-platform.prod_el.onboarding_mascot_metrics`
WHERE error IS NOT NULL
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
ORDER BY timestamp DESC
LIMIT 20;
```

**Common Error Patterns:**

**Error: "Collection 'MascotHelpArticles' not found"**
```
CAUSE: Weaviate collections not populated
FIX:
  1. Go to Weaviate console: https://console.weaviate.cloud
  2. Verify collections exist:
     - MascotHelpArticles
     - MascotQAPairs
  3. If missing, trigger data upload in Dagster:
     - MascotHelpArticles: Run the documentation upload asset
     - MascotQAPairs: Run the Q&A pairs upload asset
  4. Verify collections populated in Weaviate console
```

**Error: "OpenAI API error: Rate limit exceeded"**
```
CAUSE: Too many requests to OpenAI
FIX:
  1. Check OpenAI dashboard for rate limits
  2. Temporarily reduce traffic:
     - Set max_instances=2 in Cloud Run
  3. Upgrade OpenAI tier if needed
  4. Add exponential backoff in code (future improvement)
```

**Error: "Firestore permission denied"**
```
CAUSE: Service account lacks Firestore permissions
FIX:
  1. Grant permission (see step 5 in "Bot Stops Responding")
  2. Restart service
```

**Error: "Timeout waiting for LLM response"**
```
CAUSE: OpenAI taking too long (>300s)
FIX:
  1. Check OpenAI status: https://status.openai.com
  2. Reduce reasoning effort in config:
     reasoning = {"effort": "minimal"}
  3. Reduce RAG_TOP_K to lower token count
```

**2. Check Cloud Run Logs for Stack Traces (3 minutes)**
```bash
# Get detailed error logs with stack traces
gcloud logging read \
  'resource.labels.service_name=onboarding-assistant AND severity>=ERROR' \
  --limit=10 \
  --format=json | jq '.[] | {time: .timestamp, error: .jsonPayload.message}'
```

**3. Test Specific Error Case (5 minutes)**

If error is reproducible:

```bash
# SSH into Cloud Run instance (if possible)
# Or test locally:
cd /workspaces/py/projects/onboarding_mascot
source ../../.env
python -m src.integrations.slack.app

# Then test in Slack
# Watch local logs for detailed error
```

**4. Temporary Mitigation**

If error affects all users:

```bash
# Option 1: Rollback to previous version
gcloud run services update-traffic onboarding-assistant \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1

# Option 2: Disable bot temporarily
# Go to Slack App settings → Deactivate
# Post message in #data-questions:
# "Onboarding bot temporarily down for maintenance. Back soon!"
```

### Log Messages Reference

**Success Messages:**
```
✅ Onboarding Bot initialized successfully
✅ Connected to Weaviate successfully
✅ Firestore conversation store initialized
✅ Retrieved 5 chunks in 45.2ms
📊 Token usage: input=2775, output=200
✅ Response sent successfully
💾 Saved 2 messages to C123_1700000001
```

**Warning Messages:**
```
⚠️ Firestore not initialized, returning empty history
⚠️ No relevant documentation found for query
⚠️ Slow response time: 8.5s
```

**Error Messages:**
```
❌ Failed to connect to Weaviate: [error]
❌ Error retrieving history: [error]
❌ Error calling LLM: [error]
❌ Failed to send response to Slack: [error]
```

### Escalation Path

**If you can't resolve within 30 minutes:**

1. **Post in #data-questions:**
   ```
   🚨 Onboarding bot is down. Working on it.
   Current status: [brief description]
   ETA: [estimate or "investigating"]
   ```

2. **Contact:**
   - Data team lead
   - GCP admin (for infrastructure issues)
   - OpenAI support (for API issues)

3. **Temporary workaround:**
   - Direct users to documentation links
   - Provide manual support in #data-questions

---

## 🔌 Integration Architecture

### Platform-Agnostic Design

The core bot logic (`core/` module) has **ZERO dependencies** on Slack. This makes it easy to add new platforms.

**Architecture:**
```
┌─────────────────────────────────────────────┐
│         PLATFORM LAYER                      │
│  (integrations/slack/, integrations/discord/)│
│  - Handle platform-specific events          │
│  - Format responses for platform            │
│  - Manage platform authentication           │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         CORE LAYER (Platform-Agnostic)      │
│  - bot.py: RAG + LLM orchestration          │
│  - storage.py: Conversation history         │
│  - config.py: Configuration management      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         RAG LAYER                           │
│  - retriever.py: Weaviate search            │
│  - models.py: Data structures               │
└─────────────────────────────────────────────┘
```

### Current Integration: Slack

**Files:**
- `integrations/slack/app.py` - FastAPI + Slack Bolt server
- `integrations/slack/handlers.py` - Event processing
- `integrations/slack/config.py` - Slack credentials

**Event Flow:**
```
Slack → Webhook → FastAPI → Slack Bolt → Handler → Core Bot → Response
```

**Slack-Specific Features:**
- Event deduplication
- Markdown formatting (*single asterisks*)
- 4000 character limit handling
- Thread-based conversations

---

## 🔄 Moving to Other Platforms

### Adding a New Integration (e.g., Discord)

**Step 1: Create Integration Directory**
```bash
mkdir -p src/integrations/discord
touch src/integrations/discord/__init__.py
touch src/integrations/discord/app.py
touch src/integrations/discord/handlers.py
touch src/integrations/discord/config.py
```

**Step 2: Implement Discord App** (`discord/app.py`)

```python
"""Discord Integration - Main Entry Point"""
import discord
from discord.ext import commands
from src.core.bot import OnboardingBot
from src.core.storage import FirestoreConversationStore

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
discord_bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize core bot (platform-agnostic)
onboarding_bot = OnboardingBot()
conversation_store = FirestoreConversationStore()

@discord_bot.event
async def on_message(message):
    """Handle Discord messages"""
    if message.author == discord_bot.user:
        return

    # Get conversation history
    thread_key = f"{message.channel.id}_{message.id}"
    previous_context = None

    if conversation_store:
        history = await conversation_store.get_history(thread_key)
        if history:
            previous_context = {
                "user_question": history[-2]["content"],
                "bot_response": history[-1]["content"]
            }

    # RAG retrieval
    rag_result = onboarding_bot.retriever.retrieve(
        query=message.content,
        top_k=5,
        similarity_threshold=0.4
    )

    # LLM processing (SAME as Slack!)
    response, _, _, _, _, _ = await onboarding_bot.process_message(
        message=message.content,
        rag_result=rag_result,
        previous_context=previous_context
    )

    # Send response (Discord-specific)
    await message.channel.send(response)

    # Save conversation
    if conversation_store:
        await conversation_store.add_messages(
            thread_key,
            [
                {"role": "user", "content": message.content},
                {"role": "assistant", "content": response}
            ]
        )

# Run bot
discord_bot.run(DISCORD_TOKEN)
```

**Step 3: Discord Configuration** (`discord/config.py`)

```python
"""Discord-Specific Configuration"""
import os

class DiscordConfig:
    def __init__(self):
        self.discord_token = os.getenv("DISCORD_BOT_TOKEN")
        if not self.discord_token:
            raise ValueError("DISCORD_BOT_TOKEN required")

discord_config = DiscordConfig()
```

**Step 4: Update Dockerfile**

```dockerfile
# Add Discord dependencies
RUN pip install discord.py

# Change CMD to Discord app
CMD ["python", "-m", "src.integrations.discord.app"]
```

**That's it!** The core bot logic remains unchanged.

### Adding Web API Integration

**Use Case:** Embed bot in website chat widget

**Step 1: Create FastAPI Endpoint** (`integrations/web/app.py`)

```python
"""Web API Integration"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.core.bot import OnboardingBot
from src.core.storage import FirestoreConversationStore

app = FastAPI()
onboarding_bot = OnboardingBot()
conversation_store = FirestoreConversationStore()

class ChatRequest(BaseModel):
    message: str
    session_id: str
    previous_messages: list = []

class ChatResponse(BaseModel):
    response: str
    chunks_used: list
    processing_time_ms: float

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Handle chat request from web widget

    POST /chat
    {
      "message": "How do I use templates?",
      "session_id": "user123_session456",
      "previous_messages": [...]
    }
    """
    # Get conversation history
    previous_context = None
    if request.previous_messages:
        previous_context = {
            "user_question": request.previous_messages[-2],
            "bot_response": request.previous_messages[-1]
        }

    # RAG retrieval
    rag_result = onboarding_bot.retriever.retrieve(
        query=request.message,
        top_k=5,
        similarity_threshold=0.4
    )

    # LLM processing (SAME as Slack and Discord!)
    response, _, _, _, _, _ = await onboarding_bot.process_message(
        message=request.message,
        rag_result=rag_result,
        previous_context=previous_context
    )

    # Save conversation
    await conversation_store.add_messages(
        request.session_id,
        [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": response}
        ]
    )

    return ChatResponse(
        response=response,
        chunks_used=[
            {"tool": c.tool, "section": c.section, "similarity": c.similarity}
            for c in rag_result.chunks
        ],
        processing_time_ms=rag_result.retrieval_time_ms
    )
```

**Step 2: Frontend Integration**

```javascript
// Web widget JavaScript
async function sendMessage(message) {
  const response = await fetch('https://your-api.com/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      message: message,
      session_id: getUserSessionId(),
      previous_messages: getConversationHistory()
    })
  });

  const data = await response.json();
  displayBotResponse(data.response);
}
```

---

## 📊 Data Management

### Weaviate Collections

#### Collection 1: MascotHelpArticles

**Purpose:** Store documentation chunks

**Schema:**
```python
{
  "class": "MascotHelpArticles",
  "vectorizer": "text2vec-openai",
  "properties": [
    {"name": "tool", "dataType": ["text"]},
    {"name": "section", "dataType": ["text"]},
    {"name": "content", "dataType": ["text"]},
    {"name": "video_url", "dataType": ["text"]},
    {"name": "created_at", "dataType": ["date"]}
  ]
}
```

**Data Upload Process:**

✅ **IMPLEMENTED IN DAGSTER**

The data upload pipeline runs as a Dagster asset that:
1. Downloads .docx files from Google Drive (Onboarding Docs folder)
2. Parses documents and chunks by section headers
3. Uploads to Weaviate with OpenAI embeddings
4. Scheduled to run daily to keep documentation up-to-date

**Source:** Google Drive → Onboarding Docs folder
**Management:** Access Dagster UI to trigger manually or view scheduled runs

#### Collection 2: MascotQAPairs

**Purpose:** Store customer support Q&A pairs

**Schema:**
```python
{
  "class": "MascotQAPairs",
  "vectorizer": "text2vec-openai",
  "properties": [
    {"name": "qa_pair", "dataType": ["text"]},
    {"name": "topic", "dataType": ["text"]},
    {"name": "created_at", "dataType": ["date"]}
  ]
}
```

**Data Upload Process:**

✅ **IMPLEMENTED IN DAGSTER**

The Q&A pairs upload pipeline runs as a Dagster asset that:
1. Queries Intercom conversations from BigQuery (last 90 days, resolved tickets)
2. Formats as Q&A pairs: "Q: [user_message]\nA: [agent_response]"
3. Uploads to Weaviate with OpenAI embeddings
4. Scheduled to run daily to keep Q&A knowledge base current

**Source:** BigQuery → `kittl-data-platform.intercom.conversations`
**Management:** Access Dagster UI to trigger manually or view scheduled runs

### Firestore Structure

**Collection:** `onboarding_conversations`

**Document Structure:**
```javascript
// Document ID: "{channel_id}_{thread_ts}"
{
  "created_at": Timestamp,
  "updated_at": Timestamp,
  "messages": [
    {
      "role": "user",
      "content": "How do I use templates?"
    },
    {
      "role": "assistant",
      "content": "To use templates, click the Templates icon..."
    }
  ]
}
```

**Retention:** Indefinite (for conversation continuity)

**Cleanup (Optional):**
```python
# Delete conversations older than 90 days
from google.cloud import firestore
from datetime import datetime, timedelta

db = firestore.Client(project="kittl-data-platform")
collection = db.collection("onboarding_conversations")

cutoff = datetime.utcnow() - timedelta(days=90)

docs = collection.where("updated_at", "<", cutoff).stream()
for doc in docs:
    doc.reference.delete()
```

---

## ⚙️ Configuration Reference

### Environment Variables

**🔐 Credentials Storage:** All environment variables are stored in **1Password** under **"mascot env vars"** (managed by Syed).

**Required Variables:**

| Variable | Required | Default | Description | Where to Get |
|----------|----------|---------|-------------|-------------|
| `ONBOARDING_SLACK_BOT_TOKEN` | Yes | - | Slack bot token (xoxb-...) | Slack App → OAuth & Permissions |
| `ONBOARDING_SLACK_SIGNING_SECRET` | Yes | - | Slack signing secret | Slack App → Basic Information |
| `OPENAI_API_KEY_DATA_BOT` | Yes | - | OpenAI API key | https://platform.openai.com/api-keys |
| `WEAVIATE_URL` | Yes | - | Weaviate cluster URL (full HTTPS URL) | https://console.weaviate.cloud → Cluster Details |
| `WEAVIATE_API_KEY` | Yes | - | Weaviate API key | https://console.weaviate.cloud → Cluster → API Keys |
| `WEAVIATE_COLLECTION` | No | `MascotHelpArticles` | Main collection name | - |
| `GOOGLE_CLOUD_PROJECT` | Yes | - | GCP project ID (`kittl-data-platform`) | GCP Console |
| `RAG_TOP_K` | No | `5` | Number of chunks to retrieve | - |
| `RAG_SIMILARITY_THRESHOLD` | No | `0.4` | Minimum similarity score (0.0-1.0) | - |
| `DEBUG` | No | `false` | Enable debug logging | - |
| `ENVIRONMENT` | No | `development` | Environment name (dev/staging/production) | - |

**For Local Development (.env file):**

All variables listed above should be set in your local `.env` file (source from 1Password).

**For Cloud Run Deployment:**

All variables are automatically set by `deploy.sh` script from your local `.env` file.

### Important URLs & Resources

#### Slack App Management

**Main Dashboard:**
- https://api.slack.com/apps

**Your App Settings:**
- https://api.slack.com/apps → [Your App Name]

**Event Subscriptions (Webhook URL):**
- https://api.slack.com/apps → Your App → Event Subscriptions
- Request URL: `https://onboarding-assistant-xxx.run.app/slack/events`

**OAuth & Permissions (Bot Token):**
- https://api.slack.com/apps → Your App → OAuth & Permissions

**Basic Information (Signing Secret):**
- https://api.slack.com/apps → Your App → Basic Information

#### OpenAI

**API Keys:**
- https://platform.openai.com/api-keys

**Usage Dashboard:**
- https://platform.openai.com/usage

**Model Used:** `gpt-5-mini` (OpenAI Responses API)

#### Weaviate Cloud

**Console:**
- https://console.weaviate.cloud

**Your Cluster:**
- https://console.weaviate.cloud → [Your Cluster Name]

**Collections Used:**
- `MascotHelpArticles` (main documentation)
- `MascotQAPairs` (Q&A pairs)

#### Google Cloud Platform

**Project:** `kittl-data-platform`

**Cloud Run Console:**
- https://console.cloud.google.com/run?project=kittl-data-platform

**Service Name:** `onboarding-assistant`
**Region:** `us-central1`

**Cloud Run Service URL:**
- Format: `https://onboarding-assistant-[hash]-uc.a.run.app`
- Get current URL: `gcloud run services describe onboarding-assistant --region=us-central1 --format="value(status.url)"`

**Firestore Console:**
- https://console.firebase.google.com/project/kittl-data-platform/firestore
- Collection: `onboarding_conversations`

**BigQuery Console:**
- https://console.cloud.google.com/bigquery?project=kittl-data-platform
- Table: `kittl-data-platform.prod_el.onboarding_mascot_metrics`

**Artifact Registry:**
- https://console.cloud.google.com/artifacts?project=kittl-data-platform
- Repository: `cloud-run-images`
- Location: `us-central1`
- Image: `us-central1-docker.pkg.dev/kittl-data-platform/cloud-run-images/onboarding-assistant:latest`

### Service Account Permissions

**Cloud Run Service Account needs:**

```bash
# Firestore access
roles/datastore.user

# BigQuery logging
roles/bigquery.dataEditor
```

**Grant commands:**
```bash
gcloud projects add-iam-policy-binding kittl-data-platform \
  --member="serviceAccount:SERVICE_ACCOUNT@kittl-data-platform.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding kittl-data-platform \
  --member="serviceAccount:SERVICE_ACCOUNT@kittl-data-platform.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
```

### Slack App Configuration

**Required OAuth Scopes:**
- `app_mentions:read` - Read @mentions
- `chat:write` - Send messages
- `im:history` - Read DM history
- `im:read` - Access DMs
- `im:write` - Send DMs

**Event Subscriptions:**
- `app_mention` - When bot is @mentioned
- `message.im` - Direct messages to bot

**Request URL (after deployment):**
```
https://onboarding-assistant-[hash]-uc.a.run.app/slack/events
```
Must show ✅ green checkmark for verification

### Database/Storage Details

#### Firestore

```
Database: (default)
Mode: Native
Location: us-central1
Collection: onboarding_conversations

Document ID Format: {channel_id}_{thread_ts}
Example: C07172ECUP3_1234567890.123456
```

#### BigQuery

```
Project: kittl-data-platform
Dataset: prod_el
Table: onboarding_mascot_metrics

Full table name:
kittl-data-platform.prod_el.onboarding_mascot_metrics
```

#### Weaviate Collections

**Collection 1: MascotHelpArticles**
- Vectorizer: `text2vec-openai`
- Properties: `tool`, `section`, `content`, `video_url`, `created_at`

**Collection 2: MascotQAPairs**
- Vectorizer: `text2vec-openai`
- Properties: `qa_pair`, `topic`, `created_at`

### Deployment Configuration

**Cloud Run Settings:**
```yaml
Service Name: onboarding-assistant
Region: us-central1
Memory: 512Mi
CPU: 1
Timeout: 300s (5 minutes)
Max Instances: 10
Min Instances: 1  # Always warm (eliminates cold starts)
Port: 8080
```

**Artifact Registry:**
```
Repository: cloud-run-images
Location: us-central1
Format: Docker
Image Name: us-central1-docker.pkg.dev/kittl-data-platform/cloud-run-images/onboarding-assistant:latest
```

### Quick Commands

**Deploy to Cloud Run:**
```bash
cd /workspaces/py/projects/onboarding_mascot
source ../../.env
./deploy.sh
```

**View Logs:**
```bash
# Recent logs
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=onboarding-assistant' \
  --limit=50 \
  --project=kittl-data-platform

# Stream logs (real-time)
gcloud beta run services logs tail onboarding-assistant \
  --region=us-central1 \
  --project=kittl-data-platform
```

**Get Service URL:**
```bash
gcloud run services describe onboarding-assistant \
  --region=us-central1 \
  --format="value(status.url)"
```

**Local Development:**
```bash
cd /workspaces/py/projects/onboarding_mascot
source ../../.env
python -m src.integrations.slack.app

# Server starts at http://0.0.0.0:8080
```

### Code Configuration

**File:** `src/core/config.py`

```python
# OpenAI
openai_model = "gpt-5-mini"  # LLM model

# RAG
rag_top_k = 5  # Chunks to retrieve
rag_similarity_threshold = 0.4  # Min score

# Server
host = "0.0.0.0"
port = 8080

# BigQuery
bigquery_project = "kittl-data-platform"
bigquery_dataset = "prod_el"
bigquery_table = "onboarding_mascot_metrics"
```

### Tuning Guide

**For Better Quality:**
```python
# Retrieve more chunks
RAG_TOP_K = 7

# Higher similarity threshold
RAG_SIMILARITY_THRESHOLD = 0.5

# More reasoning
reasoning = {"effort": "medium"}
```

**For Faster Responses:**
```python
# Fewer chunks
RAG_TOP_K = 3

# Lower threshold
RAG_SIMILARITY_THRESHOLD = 0.3

# Less reasoning
reasoning = {"effort": "minimal"}
```

**For Lower Costs:**
```python
# Fewer chunks = fewer tokens
RAG_TOP_K = 3

# Shorter responses
text = {"verbosity": "low"}

# Strip more from docs
# (modify retriever.py)
```

---

## 📁 Python Files Reference

### Core Module (`src/core/`)

#### `bot.py` - Main Bot Orchestrator

**Lines of Code:** ~295
**Dependencies:** OpenAI, Weaviate retriever, config

**Class: `OnboardingBot`**

**Key Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `__init__()` | Initialize bot, retriever, load system prompt | None |
| `_load_system_prompt()` | Load personality from txt file | str |
| `process_message()` | Main processing: RAG + LLM | tuple[str, str, int, int, int, int] |
| `close()` | Clean up resources | None |

**Important Code Sections:**

The `process_message()` method orchestrates the entire RAG + LLM pipeline:
1. Builds system prompt with RAG context
2. Adds conversation history if follow-up
3. Calls OpenAI Responses API
4. Extracts response and token metrics

**Configuration Used:**
- `config.openai_model` - LLM model name
- `config.openai_api_key` - API key
- `config.system_prompt_file` - Path to prompt

#### `config.py` - Configuration Management

**Lines of Code:** ~164
**Dependencies:** os, pathlib

**Class: `CoreConfig`**

**Configuration Sections:**

| Section | Variables | Purpose |
|---------|-----------|---------|
| **OpenAI** | `openai_api_key`, `openai_model` | LLM configuration |
| **Weaviate** | `weaviate_url`, `weaviate_api_key`, `weaviate_collection` | Vector DB |
| **RAG** | `rag_top_k`, `rag_similarity_threshold` | Retrieval settings |
| **Server** | `host`, `port` | Server binding |
| **BigQuery** | `bigquery_project`, `bigquery_dataset`, `bigquery_table` | Logging |

**Important Methods:**
- `_get_system_prompt_path()` - Finds system prompt file in multiple locations
- `validate()` - Validates all required configuration

**Default Values:**
```python
openai_model = "gpt-5-mini"
rag_top_k = 5
rag_similarity_threshold = 0.4
host = "0.0.0.0"
port = 8080
```

#### `storage.py` - Firestore Conversation Storage

**Lines of Code:** ~130
**Dependencies:** google-cloud-firestore

**Class: `FirestoreConversationStore`**

**Key Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `__init__()` | Initialize Firestore client | None |
| `get_history()` | Retrieve last N messages | List[Dict] |
| `add_messages()` | Append messages to thread | None |
| `clear_history()` | Delete thread history | None |

**Thread Key Format:**
```python
thread_key = f"{channel_id}_{thread_ts}"
# Example: "C07172ECUP3_1234567890.123456"
```

### RAG Module (`src/rag/`)

#### `retriever.py` - Weaviate Search

**Lines of Code:** ~274
**Dependencies:** weaviate-client, openai

**Class: `WeaviateRetriever`**

**Key Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `__init__()` | Connect to Weaviate | None |
| `_connect()` | Establish connection | None |
| `_query_collection()` | Query single collection | List[RetrievedChunk] |
| `retrieve()` | Main retrieval (dual-collection) | RAGResult |
| `close()` | Close connection | None |

**Important:** The `retrieve()` method implements the dual-collection strategy, querying both MascotHelpArticles and MascotQAPairs, then combining and sorting results by similarity.

**Connection Configuration:**
```python
weaviate.connect_to_weaviate_cloud(
    cluster_url=weaviate_url,
    auth_credentials=weaviate.auth.AuthApiKey(api_key),
    headers={"X-OpenAI-Api-Key": openai_key}
)
```

#### `models.py` - Data Models

**Lines of Code:** ~129
**Dependencies:** dataclasses, datetime

**Data Classes:**

**1. RetrievedChunk**
```python
@dataclass
class RetrievedChunk:
    """Single chunk from Weaviate"""
    tool: str          # "Templates Tool"
    section: str       # "How to Use"
    content: str       # Actual text
    similarity: float  # 0-1 score
    rank: int         # Position (1-indexed)
    source: str       # "docs" or "qa"
```

**2. RAGResult**
```python
@dataclass
class RAGResult:
    """Complete retrieval result"""
    query: str                    # User's question
    chunks: List[RetrievedChunk] # Retrieved docs
    retrieval_time_ms: float     # Timing
    total_chunks_found: int      # Before filtering
    chunks_returned: int         # After filtering
    timestamp: datetime

    def get_context_for_llm(self) -> str:
        """Format chunks for system prompt"""
```

**3. ProcessingMetrics**
```python
@dataclass
class ProcessingMetrics:
    """Performance tracking"""
    retrieval_time_ms: float
    llm_time_ms: float
    total_time_ms: float
    chunks_retrieved: int
    tokens_used: Optional[int]
```

### Integration Module (`src/integrations/slack/`)

#### `app.py` - FastAPI + Slack Bolt Server

**Lines of Code:** ~233
**Dependencies:** fastapi, slack-bolt, dotenv

**Key Components:**

1. **Slack App Initialization** - Creates AsyncApp with bot token and signing secret
2. **Event Handlers** - Registers handlers for app_mention and message events
3. **FastAPI Application** - Sets up web server with lifespan management
4. **Endpoints:**
   - `/slack/events` (POST) - Slack webhook receiver
   - `/health` (GET) - Health check
   - `/` (GET) - Service info

**Important:** The `/slack/events` endpoint handles URL verification, deduplication, and processes events in the background to acknowledge within 3 seconds.

#### `handlers.py` - Event Processing Logic

**Lines of Code:** ~391
**Dependencies:** slack-bolt, google-cloud-bigquery

**Class: `SlackEventHandler`**

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `handle_app_mention()` | Process @mentions |
| `handle_message()` | Process DMs |
| `_process_and_respond()` | Main processing pipeline |
| `_log_to_bigquery()` | Log metrics |

**Important:** The `_process_and_respond()` method implements the complete pipeline:
1. Get conversation history from Firestore
2. Retrieve docs from Weaviate (RAG)
3. Call LLM with context
4. Send response to Slack
5. Save conversation to Firestore
6. Log metrics to BigQuery

#### `config.py` - Slack Configuration

**Lines of Code:** ~50
**Dependencies:** os

**Class: `SlackConfig`**

**Configuration:**
```python
class SlackConfig:
    def __init__(self):
        # Bot token (xoxb-...)
        self.slack_bot_token = os.getenv("ONBOARDING_SLACK_BOT_TOKEN")

        # Signing secret for verification
        self.slack_signing_secret = os.getenv("ONBOARDING_SLACK_SIGNING_SECRET")
```

---

**End of Handover Document**

*Last Updated: January 2026*
*Document Owner: Syed*
*Next Review: After Dagster migration*
