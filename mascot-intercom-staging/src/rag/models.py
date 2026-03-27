"""Data Models for RAG System.

This module defines the data structures used throughout the RAG pipeline, including
retrieved chunks, query results, and timing information.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class RetrievedChunk:
    """Represents a single chunk retrieved from Weaviate.

    Attributes:
        tool: Name of the Kittl tool (e.g., "Templates Tool", "Mockups Tool")
        section: Section within the tool docs (e.g., "Tool Description", "How to Use")
        content: The actual documentation text (clean, without metadata)
        similarity: Similarity score from vector search (0-1, higher is better)
        rank: Position in the retrieved results (1-indexed)
        source: Source collection ("docs" or "qa")
    """

    tool: str
    section: str
    content: str
    similarity: float
    rank: int
    source: str = "docs"  # Default to docs for backward compatibility

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"Chunk #{self.rank}: {self.tool} - {self.section} "
            f"(similarity: {self.similarity:.4f}, source: {self.source})"
        )


@dataclass
class RAGResult:
    """Complete result from a RAG retrieval operation.

    This includes all retrieved chunks plus timing and metadata
    for logging and monitoring purposes.

    Attributes:
        query: The original user query
        chunks: List of retrieved documentation chunks
        retrieval_time_ms: Time taken to retrieve from Weaviate (milliseconds)
        total_chunks_found: Total number of chunks found in Weaviate
        chunks_returned: Number of chunks actually returned (top-K)
        timestamp: When this retrieval happened
    """

    query: str
    chunks: List[RetrievedChunk]
    retrieval_time_ms: float
    total_chunks_found: int
    chunks_returned: int
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_context_for_llm(self) -> str:
        """Format retrieved chunks as context string for the LLM.

        This creates a structured string that will be included in the
        system message to provide relevant documentation context.

        Returns:
            Formatted string with all chunk contents
        """
        if not self.chunks:
            return "No relevant documentation found for this query."

        context_parts = [
            "Here is relevant documentation to help answer the user's question:\n"
        ]

        for chunk in self.chunks:
            context_parts.append(
                f"\n--- {chunk.tool}: {chunk.section} ---\n{chunk.content}\n"
            )

        return "\n".join(context_parts)

    def get_log_summary(self) -> str:
        """Get a summary string for logging purposes.

        Returns:
            Human-readable summary of retrieval results
        """
        return (
            f"Retrieved {self.chunks_returned} chunks in"
            f" {self.retrieval_time_ms:.2f}ms. Top result: {self.chunks[0]}"
            if self.chunks
            else "No chunks retrieved."
        )


@dataclass
class ProcessingMetrics:
    """Timing and performance metrics for a complete message processing cycle.

    This helps track latency and identify bottlenecks in the pipeline.

    Attributes:
        retrieval_time_ms: Time to retrieve chunks from Weaviate
        llm_time_ms: Time for OpenAI API call
        total_time_ms: Total end-to-end processing time
        chunks_retrieved: Number of chunks retrieved
        tokens_used: Approximate tokens used in LLM call (if available)
    """

    retrieval_time_ms: float
    llm_time_ms: float
    total_time_ms: float
    chunks_retrieved: int
    tokens_used: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"Metrics: Total={self.total_time_ms:.2f}ms "
            f"(Retrieval={self.retrieval_time_ms:.2f}ms, "
            f"LLM={self.llm_time_ms:.2f}ms), "
            f"Chunks={self.chunks_retrieved}"
        )
