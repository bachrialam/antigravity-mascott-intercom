"""Intercom webhook handling - payload parsing and mascot core invocation.

This module is isolated from Slack. It:
- Parses Intercom webhook payloads safely
- Extracts user message text from conversation events
- Invokes mascot core (RAG + LLM) when the payload is safe and relevant
- Sends the LLM response back to Intercom via API
"""

import asyncio
import logging
from typing import Any, Optional, Tuple

from ...core.bot import OnboardingBot
from .client import intercom_client

logger = logging.getLogger(__name__)

# Only process these Intercom topics (user-sent messages)
ALLOWED_TOPICS = frozenset({
    "conversation.user.created",
    "conversation.user.replied",
})

# Safety limits for extracted message
MAX_MESSAGE_LENGTH = 10_000
MIN_MESSAGE_LENGTH = 1

# Simple in-memory state for bot attempt capping
# Key: conversation_id, Value: number of failed bot loops ("no" responses or confusing inputs)
bot_failure_counts: dict[str, int] = {}

# In-memory tracking of conversations that have been handed off to human support.
# If a conversation is in this set, the bot will ignore all subsequent messages.
handed_off_conversations: set[str] = set()


def extract_message_from_payload(payload: dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Extract user message text AND conversation ID from an Intercom webhook payload safely.

    Handles conversation webhook structure:
    - data.item.conversation_message.body (initial message)
    - data.item.conversation_parts.conversation_parts (replies; last user part)

    Args:
        payload: Raw JSON body of the webhook (e.g. from request.json()).

    Returns:
        Tuple (message_text, conversation_id).
        If invalid/not found, returns (None, None).
    """
    if not payload or not isinstance(payload, dict):
        return None, None

    topic = payload.get("topic")
    if topic not in ALLOWED_TOPICS:
        return None, None

    data = payload.get("data") or {}
    item = data.get("item") if isinstance(data, dict) else {}
    if not isinstance(item, dict):
        return None, None

    # Extract conversation ID
    conversation_id = item.get("id")
    if not conversation_id:
        return None, None

    # Try conversation_parts first (for replies: last user comment)
    parts_container = item.get("conversation_parts")
    if isinstance(parts_container, dict):
        parts_list = parts_container.get("conversation_parts")
        if isinstance(parts_list, list) and parts_list:
            for part in reversed(parts_list):
                if not isinstance(part, dict):
                    continue
                author = part.get("author") or {}
                if isinstance(author, dict) and author.get("type") == "user":
                    body = part.get("body")
                    if isinstance(body, str):
                        text = body.strip()
                        if MIN_MESSAGE_LENGTH <= len(text) <= MAX_MESSAGE_LENGTH:
                            return text, conversation_id
            # If we went through all parts and found no user message, we fall through

    # Fallback 1: initial conversation message
    conv_msg = item.get("conversation_message")
    if isinstance(conv_msg, dict):
        body = conv_msg.get("body")
        if isinstance(body, str):
            text = body.strip()
            if MIN_MESSAGE_LENGTH <= len(text) <= MAX_MESSAGE_LENGTH:
                return text, conversation_id

    # Fallback 2: source (often used in conversation.user.created)
    if payload.get("topic") == "conversation.user.created":
         source = item.get("source", {})
         body = source.get("body")
         if isinstance(body, str):
            text = body.strip()
            if MIN_MESSAGE_LENGTH <= len(text) <= MAX_MESSAGE_LENGTH:
                return text, conversation_id

    return None, conversation_id


async def _run_mascot_core(bot: OnboardingBot, message: str, conversation_id: str) -> None:
    """Core logic wrapper to be run in background."""
    try:
        # 0. Check Handoff State
        if conversation_id in handed_off_conversations:
            logger.info("Conversation %s already handed off to human. Ignoring message.", conversation_id)
            return

        # 0.5 Check for Escape Hatch Keywords or Explicit Feedback
        msg_lower = message.lower().strip()
        # Clean up HTML tags if any sneaked through, since the content might be wrapped in <p>
        msg_lower = msg_lower.replace("<p>", "").replace("</p>", "").strip()
        
        escape_keywords = {"human", "agent", "support", "someone", "representative", "talk to a person"}
        is_escape = any(kw in msg_lower for kw in escape_keywords)

        is_yes = msg_lower in {"yes", "yeah", "yep", "y"}
        is_no = msg_lower in {"no", "nope", "nah", "n"}

        if is_yes:
            # Close loop
            await intercom_client.send_reply(conversation_id, "Great — anything else?")
            logger.info("Conversation %s marked as resolved by user.", conversation_id)
            bot_failure_counts.pop(conversation_id, None)
            return

        if is_no or is_escape:
            # Handoff Logic
            bot_failure_counts[conversation_id] = bot_failure_counts.get(conversation_id, 0) + 1
            failures = bot_failure_counts[conversation_id]
            
            if is_escape:
                 await intercom_client.send_reply(conversation_id, "I'm routing you to a human representative now.")
            else:
                 await intercom_client.send_reply(conversation_id, "Got it — I'm looping in support now.")
            
            # The bot should stop replying from now on
            handed_off_conversations.add(conversation_id)
            
            # Assigning to the main queue (0)
            await intercom_client.assign_conversation(
                conversation_id, assignee_id="0"
            )
            logger.info("Conversation %s handed off to human support. Escape=%s, Failures=%d", conversation_id, is_escape, failures)
            return

        # Check capping
        failures = bot_failure_counts.get(conversation_id, 0)
        if failures >= 2:
            # Force handoff if we've already failed twice
            await intercom_client.send_reply(conversation_id, "It seems I'm still not quite getting it. I'm looping in human support to help you out.")
            handed_off_conversations.add(conversation_id)
            await intercom_client.assign_conversation(
                conversation_id, assignee_id="0"
            )
            logger.info("Conversation %s strictly capped and handed off.", conversation_id)
            return

        # 1. Immediate Acknowledgement (Typing Indicator Workaround)
        # Send a quick "status" message so the user knows we are working on it.
        await intercom_client.send_reply(conversation_id, "🔍 Reading...")

        # 1. Fetch Conversation History (for context)
        conversation_history = []
        try:
            conv_data = await intercom_client.get_conversation(conversation_id)
            if conv_data:
                # 1. Initial message
                raw_msgs = []
                init_msg = conv_data.get("conversation_message", {})
                if init_msg.get("body"):
                    raw_msgs.append({
                        "role": "user", # Initial message is always user in this context
                        "content": init_msg["body"],
                        "author_type": init_msg.get("author", {}).get("type")
                    })
                
                # 2. Replies (conversation_parts)
                parts = conv_data.get("conversation_parts", {}).get("conversation_parts", [])
                for part in parts:
                    if part.get("body"):
                        role = "assistant" if part.get("author", {}).get("type") == "admin" else "user"
                        raw_msgs.append({
                            "role": role,
                            "content": part["body"],
                            "author_type": part.get("author", {}).get("type")
                        })
                
                # 3. Filter and Format
                # We want to exclude the *current* message because `bot.process_message`
                # takes it as the `message` argument.
                # Heuristic: If the last message in history matches our current `message`, drop it.
                if raw_msgs:
                    last_msg = raw_msgs[-1]
                    if last_msg["role"] == "user" and last_msg["content"].strip() == message.strip():
                        raw_msgs.pop()
                
                # Take last N messages for context (e.g. 10)
                conversation_history = [
                    {"role": m["role"], "content": m["content"]} 
                    for m in raw_msgs[-10:]
                ]
                logger.debug("Fetched %d history messages for context", len(conversation_history))

        except Exception as e:
            logger.warning("Failed to fetch Intercom history: %s", e)

        # 1. RAG Retrieval
        rag_result = bot.retriever.retrieve(
            query=message,
            top_k=bot.config.rag_top_k,
            similarity_threshold=bot.config.rag_similarity_threshold,
        )

        # 2. LLM Processing
        # Returns tuple: (response_text, system_prompt, input_tokens, output_tokens, ..., is_complete_answer)
        response_tuple = await bot.process_message(
            message=message,
            rag_result=rag_result,
            conversation_history=conversation_history,
        )
        
        reply_text = response_tuple[0]
        # Extract is_complete_answer from the tuple (it's the 7th element: index 6)
        is_complete_answer = response_tuple[6]

        # 3. Send Reply to Intercom
        logger.info("Sending reply to Intercom conversation %s...", conversation_id)
        
        # Build quick reply buttons if this was a complete answer
        reply_options = None
        if is_complete_answer:
            import uuid
            
            reply_text += "\n\n**Did this answer your question?**"
            reply_options = [
                {"uuid": str(uuid.uuid4()), "text": "Yes"},
                {"uuid": str(uuid.uuid4()), "text": "No"},
                {"uuid": str(uuid.uuid4()), "text": "Talk to a person"}
            ]

        # Use markdown formatted reply with optional buttons
        success = await intercom_client.send_reply(
            conversation_id=conversation_id, 
            message_body=reply_text,
            reply_options=reply_options
        )
        
        if success:
            logger.info("Intercom webhook: processing & reply completed successfully.")
        else:
            logger.warning("Intercom webhook: processing done but reply FAILED.")

    except Exception as e:
        logger.error("Intercom webhook: mascot core processing failed: %s", e, exc_info=True)


from fastapi import BackgroundTasks

def process_intercom_webhook(bot: OnboardingBot, payload: dict[str, Any], background_tasks: BackgroundTasks) -> None:
    """Extract message from payload and, if safe, send to mascot core (fire-and-forget).

    Always returns quickly so the HTTP handler can respond 200 OK. Processing
    runs in the event loop as a background task.

    Args:
        bot: OnboardingBot instance (shared with app, not Slack-specific).
        payload: Parsed JSON webhook body.
        background_tasks: FastAPI BackgroundTasks object.
    """
    topic = payload.get("topic")
    logger.info("Intercom webhook received: topic=%s", topic)
    
    message, conversation_id = extract_message_from_payload(payload)
    
    if message is None or conversation_id is None:
        data = payload.get("data", {})
        item = data.get("item", {}) if isinstance(data, dict) else {}
        logger.warning(
            "Intercom webhook: no safe message/conversation_id to process. "
            "Topic: %s. Item keys: %s", 
            topic, list(item.keys()) if isinstance(item, dict) else "Not a dict"
        )
        return

    background_tasks.add_task(_run_mascot_core, bot, message, conversation_id)
    logger.info("Intercom webhook: queued mascot core processing for conv %s (staging)", conversation_id)
