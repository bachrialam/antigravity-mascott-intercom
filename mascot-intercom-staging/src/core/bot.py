"""Core Onboarding Bot Logic.

This module contains the OnboardingBot class which handles:
- Loading system prompts
- Coordinating RAG retrieval with Weaviate
- Calling OpenAI LLM with retrieved context

This is platform-agnostic - can be used with Slack, Discord, Web API, etc.
"""

import logging
from typing import Dict, Optional

from openai import AsyncOpenAI

from ..rag.models import RAGResult
from ..rag.retriever import WeaviateRetriever
from .config import config

logger = logging.getLogger(__name__)

# Initialize OpenAI client for LLM calls (shared instance)
openai_client = AsyncOpenAI(api_key=config.openai_api_key)


class OnboardingBot:
    """Core bot logic: RAG retrieval + LLM integration.

    This class handles:
    - Loading system prompts
    - Coordinating RAG retrieval with Weaviate
    - Calling OpenAI LLM with retrieved context

    This class is platform-agnostic and can be used with any interface.
    """

    def __init__(self) -> None:
        """Initialize the bot with all required components."""
        logger.info("🤖 Initializing Onboarding Bot...")

        # Store configuration reference
        self.config = config

        # Initialize Weaviate retriever for RAG
        logger.info("Connecting to Weaviate...")
        self.retriever = WeaviateRetriever(
            weaviate_url=config.weaviate_url,
            weaviate_api_key=config.weaviate_api_key,
            openai_api_key=config.openai_api_key,
            collection_name=config.weaviate_collection,
        )

        self.system_prompt = self._load_system_prompt()

        self.openai_client = openai_client

        logger.info("✅ Onboarding Bot initialized successfully")

    def _load_system_prompt(self) -> str:
        """Load the system prompt that defines the bot's personality and behavior.

        The system prompt is stored in src/config/system_prompt.txt and tells
        the LLM how to behave, what tone to use, and how to respond.

        Returns:
            System prompt text

        Raises:
            FileNotFoundError: If system_prompt.txt doesn't exist
            ValueError: If system_prompt.txt is empty
        """
        prompt_path = config.system_prompt_file

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"System prompt file not found: {prompt_path}\nPlease create"
                " src/config/system_prompt.txt with the bot's instructions."
            )

        with open(prompt_path, encoding="utf-8") as f:
            prompt = f.read().strip()

        if not prompt:
            raise ValueError(
                f"System prompt file is empty: {prompt_path}\n"
                "Please add content to src/config/system_prompt.txt"
            )

        logger.info(f"Loaded system prompt from: {prompt_path} ({len(prompt)} chars)")

        return prompt

    async def process_message(
        self,
        message: str,
        rag_result: RAGResult,
        thread_ts: Optional[str] = None,
        channel: Optional[str] = None,
        previous_context: Optional[Dict[str, str]] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> tuple[str, str, int, int, int, int, bool]:
        """Process a user message using RAG + LLM.

        This is the core method that:
        1. Builds conversation context with retrieved documentation
        2. Adds thread memory for multi-turn conversations
        3. Calls OpenAI LLM

        Args:
            message: The user's message
            rag_result: Retrieved documentation chunks from Weaviate
            thread_ts: Thread timestamp for conversation context
                (optional, platform-specific)
            channel: Channel ID (optional, platform-specific)
            previous_context: Dict with 'user_question' and 'bot_response'
                from previous turn (deprecated in favor of conversation_history)
            conversation_history: List of dicts with 'role' ('user'/'assistant')
                and 'content' representing previous chat messages.

        Returns:
            Tuple of (response_text, enhanced_system_prompt, input_tokens,
            output_tokens, cached_tokens, reasoning_tokens, is_complete_answer)
        """
        try:
            # ================================================================
            # Step 1: Build system message with retrieved documentation
            # ================================================================

            # Get formatted context from retrieved chunks
            documentation_context = rag_result.get_context_for_llm()

            # Build conversation context section (Legacy support or summary)
            # If we have full history, we rely on that mostly, but this summary
            # can still be helpful if history is truncated.
            if previous_context and not conversation_history:
                conversation_context = (
                    "\n\n--- PREVIOUS CONVERSATION CONTEXT ---\nPrevious User"
                    f" Question: {previous_context['user_question']}\nPrevious Bot"
                    f" Response: {previous_context['bot_response']}\n--- END OF"
                    " PREVIOUS CONTEXT ---\n\nNote: The user's current question may be"
                    " a follow-up to the previous conversation above. Use this context"
                    ' to better understand references like "it", "that tool",'
                    ' "how do I use it", etc.'
                )
            else:
                conversation_context = ""

            # Combine system prompt with retrieved documentation and context
            enhanced_system_prompt = (
                f"{self.system_prompt}\n\n"
                "==================================================================\n"
                "RETRIEVED DOCUMENTATION CONTEXT "
                "(from semantic search based on user's question):\n"
                "==================================================================\n"
                f"{documentation_context}\n\n"
                "Remember: Base your answers on the documentation provided above. "
                "If the documentation doesn't contain the answer, use the summary "
                "of tools to give a general overview of the tools."
                f"{conversation_context}"
            )

            # Log the full enhanced system prompt for debugging (on one line)
            logger.info("📝 FULL SYSTEM PROMPT: %s", repr(enhanced_system_prompt))

            # ================================================================
            # Step 2: Build conversation history
            # ================================================================

            # Start with system prompt
            messages = [{"role": "system", "content": enhanced_system_prompt}]

            # Add conversation history if available
            if conversation_history:
                # Ensure we only include valid roles and content
                for msg in conversation_history:
                    if msg.get("role") in ("user", "assistant") and msg.get("content"):
                        messages.append(
                            {"role": msg["role"], "content": msg["content"]}
                        )

            # Add current user message
            messages.append({"role": "user", "content": message})

            # Log what we're sending to the LLM
            logger.debug(f"📨 Sending to LLM: {len(messages)} messages")
            logger.debug(
                f"   System prompt length: {len(enhanced_system_prompt)} chars"
            )
            logger.debug(f"   User message: {message[:100]}...")

            # ================================================================
            # Step 3: Call OpenAI Chat Completions API
            # ================================================================

            logger.info(f"🧠 Calling OpenAI API ({config.openai_model})...")

            # Call OpenAI Chat Completions API
            response = await self.openai_client.chat.completions.create(
                model=config.openai_model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )

            # Extract the response text
            ai_response = response.choices[0].message.content or ""
            logger.info(f"✅ Extracted response: {ai_response[:200]}...")

            # Extract token usage for monitoring and logging
            input_tokens = 0
            output_tokens = 0
            cached_tokens = 0
            reasoning_tokens = 0

            if hasattr(response, "usage") and response.usage:
                input_tokens = response.usage.prompt_tokens or 0
                output_tokens = response.usage.completion_tokens or 0


                # Extract input token details
                if (
                    hasattr(response.usage, "input_tokens_details")
                    and response.usage.input_tokens_details
                ):
                    cached_tokens = (
                        getattr(response.usage.input_tokens_details, "cached_tokens", 0)
                        or 0
                    )
                elif (
                    hasattr(response.usage, "prompt_tokens_details")
                    and response.usage.prompt_tokens_details
                ):
                    # Fallback for older SDK versions/models
                    cached_tokens = (
                        getattr(
                            response.usage.prompt_tokens_details, "cached_tokens", 0
                        )
                        or 0
                    )

                # Extract output token details (reasoning)
                if (
                    hasattr(response.usage, "output_tokens_details")
                    and response.usage.output_tokens_details
                ):
                    reasoning_tokens = (
                        getattr(
                            response.usage.output_tokens_details, "reasoning_tokens", 0
                        )
                        or 0
                    )

                logger.info(
                    "📊 Token usage: "
                    f"input={input_tokens} (cached={cached_tokens}), "
                    f"output={output_tokens} (reasoning={reasoning_tokens}), "
                    f"total={response.usage.total_tokens}"
                )
            # Check if this appears to be a "complete" answer.
            # We use a heuristic: moderately long response that doesn't end in a question mark.
            is_complete_answer = len(ai_response.strip()) > 100 and not ai_response.strip().endswith("?")
            if "encountered an error" in ai_response.lower():
                is_complete_answer = False

            logger.info(f"✅ LLM response received ({len(ai_response)} chars)")
            logger.debug(f"Response preview: {ai_response[:200]}...")

            return (
                ai_response,
                enhanced_system_prompt,
                input_tokens,
                output_tokens,
                cached_tokens,
                reasoning_tokens,
                is_complete_answer,
            )

        except Exception as e:
            logger.error(f"❌ Error calling LLM: {e}", exc_info=True)
            error_msg = (
                "I encountered an error generating a response. "
                "Please try rephrasing your question or contact support. 🙏"
            )
            return (error_msg, "", 0, 0, 0, 0, False)

    def close(self) -> None:
        """Clean up resources.

        Call this when shutting down the application.
        """
        logger.info("🧹 Cleaning up Onboarding Bot resources...")
        if hasattr(self, "retriever"):
            self.retriever.close()
