"""Slack Event Handlers.

This module handles all Slack events including mentions and direct messages.
It processes user messages, retrieves context, calls the LLM, and sends responses.

Key responsibilities:
- Handle @mentions in channels
- Handle direct messages to the bot
- Manage thread context/memory
- Coordinate RAG retrieval and LLM calls
- Log all interactions with timing
"""

import asyncio
import logging
import time
from datetime import datetime

from slack_bolt.async_app import AsyncAck, AsyncSay

from ...core.bot import OnboardingBot
from ...core.storage import FirestoreConversationStore
from ...rag.models import ProcessingMetrics, RAGResult

# Set up logging
logger = logging.getLogger(__name__)


class SlackEventHandler:
    """Handles Slack events and coordinates the RAG + LLM pipeline.

    This class is the main orchestrator that receives Slack events, retrieves relevant
    documentation, calls the LLM, and responds.
    """

    def __init__(
        self,
        onboarding_bot: OnboardingBot,
        conversation_store: FirestoreConversationStore,
    ) -> None:
        """Initialize the event handler.

        Args:
            onboarding_bot: Instance of OnboardingBot for LLM calls
            conversation_store: Storage backend for conversation history
        """
        self.bot = onboarding_bot
        self.conversation_store = conversation_store
        logger.info("✅ Slack event handler initialized")

    async def handle_app_mention(
        self, event: dict[str, object], say: AsyncSay, ack: AsyncAck
    ) -> None:
        """Handle @mentions of the bot in channels.

        This is called when someone mentions the bot in a public or private channel.
        Example: "@OnboardingBot how do I browse templates?"

        Args:
            event: Slack event data containing the message
            say: Function to send a message back to Slack
            ack: Function to acknowledge the event (must be called within 3 seconds)
        """
        # Acknowledge the event immediately (required by Slack)
        await ack()

        # Extract message details
        text = event.get("text", "")
        user = event.get("user", "unknown")
        channel = event.get("channel", "unknown")
        thread_ts = event.get("thread_ts") or event.get(
            "ts"
        )  # Thread or message timestamp

        logger.info(f"👋 App mentioned in channel {channel} by user {user}")
        logger.info(f"📝 Message: {text[:100]}...")

        # Process the message and send response
        await self._process_and_respond(
            message=text, say=say, channel=channel, thread_ts=thread_ts, user=user
        )

    async def handle_message(
        self, event: dict[str, object], say: AsyncSay, ack: AsyncAck
    ) -> None:
        """Handle direct messages to the bot.

        This is called when someone sends a DM to the bot.
        Note: We filter out bot messages and message edits/deletions.

        Args:
            event: Slack event data containing the message
            say: Function to send a message back to Slack
            ack: Function to acknowledge the event
        """
        await ack()

        # Ignore messages from bots (including our own messages)
        if event.get("bot_id"):
            return

        # Ignore message deletions and edits
        if event.get("subtype") in ["message_deleted", "message_changed"]:
            return

        # Only handle direct messages (channel_type = "im")
        if event.get("channel_type") != "im":
            return

        # Extract message details
        text = event.get("text", "")
        user = event.get("user", "unknown")
        channel = event.get("channel", "unknown")
        thread_ts = event.get("thread_ts") or event.get("ts")

        logger.info(f"💬 DM received from user {user}")
        logger.info(f"📝 Message: {text[:100]}...")

        # Process the message and send response
        await self._process_and_respond(
            message=text, say=say, channel=channel, thread_ts=thread_ts, user=user
        )

    async def _process_and_respond(
        self, message: str, say: AsyncSay, channel: str, thread_ts: str, user: str
    ) -> None:
        """Core processing logic: RAG retrieval + LLM + response.

        This method orchestrates the entire pipeline:
        1. Enhance query with conversation context (if available)
        2. Retrieve relevant chunks from Weaviate
        3. Call OpenAI LLM with retrieved context
        4. Send response back to Slack
        5. Log everything with timing

        Args:
            message: User's message text
            say: Function to send Slack message
            channel: Slack channel ID
            thread_ts: Thread timestamp for threading
            user: User ID who sent the message
        """
        # Start timing the entire process
        total_start_time = time.time()

        try:
            # Step 1: Extract previous conversation context (if available)
            # --------------------------------------------------------
            previous_context = None

            if thread_ts and channel:
                thread_key = f"{channel}_{thread_ts}"

                # Retrieve history from Firestore
                thread_history = await self.conversation_store.get_history(
                    thread_key, limit=10
                )

                # If there's conversation history, extract the last Q&A pair
                if thread_history and len(thread_history) >= 2:
                    # Get the last user message and assistant response
                    last_user_msg = None
                    last_assistant_msg = None

                    for msg in reversed(thread_history):
                        if msg["role"] == "assistant" and last_assistant_msg is None:
                            last_assistant_msg = msg["content"]
                        elif (
                            msg["role"] == "user"
                            and last_user_msg is None
                            and last_assistant_msg is not None
                        ):
                            last_user_msg = msg["content"]
                            break

                    if last_user_msg and last_assistant_msg:
                        previous_context = {
                            "user_question": last_user_msg,
                            "bot_response": last_assistant_msg,
                        }
                        logger.info("💭 Found previous conversation context")
                        logger.debug(f"   Previous Q: {last_user_msg[:100]}...")
                        logger.debug(f"   Previous A: {last_assistant_msg[:100]}...")

            # Step 2: Retrieve relevant documentation from Weaviate
            # --------------------------------------------------------
            logger.info("🔍 Retrieving documentation from Weaviate...")

            rag_result = self.bot.retriever.retrieve(
                query=message,  # Use original message for retrieval
                top_k=self.bot.config.rag_top_k,
                similarity_threshold=self.bot.config.rag_similarity_threshold,
            )

            retrieval_time_ms = rag_result.retrieval_time_ms

            # Log what we retrieved
            logger.info(f"✅ Retrieved {rag_result.chunks_returned} chunks:")
            for chunk in rag_result.chunks:
                logger.info(f"   • {chunk}")

            # Step 3: Call LLM with retrieved context
            # ----------------------------------------
            logger.info("🤖 Calling OpenAI LLM...")

            llm_start_time = time.time()

            (
                response_text,
                system_prompt_with_context,
                input_tokens,
                output_tokens,
                cached_tokens,
                reasoning_tokens,
            ) = await self.bot.process_message(
                message=message,
                rag_result=rag_result,
                thread_ts=thread_ts,
                channel=channel,
                previous_context=previous_context,
            )

            llm_time_ms = (time.time() - llm_start_time) * 1000

            logger.info(f"✅ LLM response generated ({len(response_text)} chars)")
            logger.info(
                f"📊 Tokens: input={input_tokens}, output={output_tokens},"
                f" cached={cached_tokens}, reasoning={reasoning_tokens}"
            )

            # Step 4: Send response back to Slack
            # ------------------------------------
            logger.info("📤 Sending response to Slack...")

            await say(text=response_text, thread_ts=thread_ts)  # Reply in thread

            logger.info("✅ Response sent successfully")

            # Step 4.5: Store conversation for future context
            # ------------------------------------------------
            if thread_ts and channel:
                thread_key = f"{channel}_{thread_ts}"

                # Save messages to Firestore (asynchronously)
                new_messages = [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response_text},
                ]

                asyncio.create_task(
                    self.conversation_store.add_messages(thread_key, new_messages)
                )

            # Step 5: Calculate and log metrics
            # ----------------------------------
            total_time_ms = (time.time() - total_start_time) * 1000

            metrics = ProcessingMetrics(
                retrieval_time_ms=retrieval_time_ms,
                llm_time_ms=llm_time_ms,
                total_time_ms=total_time_ms,
                chunks_retrieved=rag_result.chunks_returned,
            )

            logger.info(f"📊 {metrics}")

            # Step 6: Log metrics to BigQuery (async, non-blocking)
            # ------------------------------------------------------
            if self.bot.config.enable_bigquery_logging:
                asyncio.create_task(
                    self._log_to_bigquery(
                        metrics=metrics,
                        user_question=message,
                        bot_response=response_text,
                        system_prompt_with_context=system_prompt_with_context,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cached_tokens=cached_tokens,
                        reasoning_tokens=reasoning_tokens,
                        rag_result=rag_result,
                        thread_ts=thread_ts,
                    )
                )

        except Exception as e:
            logger.error(f"❌ Error processing message: {e}", exc_info=True)

            # Send error message to user
            error_message = (
                "Sorry, I encountered an error processing your request. "
                "Please try again or contact support if the issue persists. 🙏"
            )

            try:
                await say(text=error_message, thread_ts=thread_ts)
            except Exception as send_error:
                logger.error(f"❌ Failed to send error message: {send_error}")

    async def _log_to_bigquery(
        self,
        metrics: ProcessingMetrics,
        user_question: str,
        bot_response: str,
        system_prompt_with_context: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
        reasoning_tokens: int,
        rag_result: RAGResult,
        thread_ts: str,
    ) -> None:
        """Log interaction to BigQuery for analytics.

        This runs asynchronously after the Slack response is sent,
        so it doesn't impact latency. Failures are logged but don't crash the bot.

        Args:
            metrics: Processing timing metrics
            user_question: The user's original question
            bot_response: The bot's response
            system_prompt_with_context: Full system prompt including RAG context
            input_tokens: Number of tokens in the input (total)
            output_tokens: Number of tokens in the bot's response
            cached_tokens: Number of cached tokens from OpenAI
            reasoning_tokens: Number of tokens used for reasoning
            rag_result: Retrieved chunks and metadata
            thread_ts: Thread timestamp
        """
        try:
            from google.cloud import bigquery

            # Initialize BigQuery client
            if self.bot.config.bigquery_credentials_path:
                client = bigquery.Client.from_service_account_json(
                    self.bot.config.bigquery_credentials_path
                )
            else:
                # Use default credentials (Application Default Credentials)
                client = bigquery.Client(project=self.bot.config.bigquery_project)

            table_id = (
                f"{self.bot.config.bigquery_project}."
                f"{self.bot.config.bigquery_dataset}."
                f"{self.bot.config.bigquery_table}"
            )

            # Format chunks for nested field
            chunks_data = [
                {
                    "rank": chunk.rank,
                    "tool": chunk.tool,
                    "section": chunk.section,
                    "similarity": chunk.similarity,
                    "content": chunk.content,
                }
                for chunk in rag_result.chunks
            ]

            # Prepare row
            row = {
                "timestamp": datetime.utcnow().isoformat(),
                "thread_ts": thread_ts or "",
                "user_question": user_question,
                "total_latency_ms": metrics.total_time_ms,
                "retrieval_time_ms": metrics.retrieval_time_ms,
                "llm_generation_ms": metrics.llm_time_ms,
                "chunks_retrieved": chunks_data,
                "system_prompt_with_context": system_prompt_with_context,
                # Responses API Token Breakdown
                "responses_input_tokens": input_tokens,
                "responses_cached_tokens": cached_tokens,
                "responses_output_tokens": output_tokens,
                "responses_reasoning_tokens": reasoning_tokens,
                "system_prompt_tokens": input_tokens,
                "output_tokens": output_tokens,
                "bot_response": bot_response,
                "error": None,
            }

            # Insert row
            errors = client.insert_rows_json(table_id, [row])

            if errors:
                logger.error(f"❌ BigQuery insert errors: {errors}")
            else:
                logger.debug(f"✅ Logged to BigQuery: {table_id}")

        except Exception as e:
            # Don't crash the bot if logging fails
            logger.error(f"❌ Failed to log to BigQuery: {e}", exc_info=True)
