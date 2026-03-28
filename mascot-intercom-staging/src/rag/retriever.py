"""Weaviate RAG Retriever.

This module handles all interactions with Weaviate for retrieving
relevant documentation chunks based on user queries.

Key responsibilities:
- Connect to Weaviate Cloud
- Perform semantic search over documentation chunks
- Format results with timing metrics
- Handle errors gracefully
"""

import logging
import time
from typing import List, Optional

import weaviate
from weaviate.classes.query import MetadataQuery

from .models import RAGResult, RetrievedChunk

# Set up logging
logger = logging.getLogger(__name__)


class WeaviateRetriever:
    """Handles retrieval of relevant documentation from Weaviate.

    This class manages the connection to Weaviate and provides methods for semantic
    search over documentation chunks.
    """

    def __init__(
        self,
        weaviate_url: str,
        weaviate_api_key: str,
        openai_api_key: str,
        collection_name: str = "MascotHelpArticles",
    ) -> None:
        """Initialize the Weaviate retriever.

        Args:
            weaviate_url: Weaviate Cloud cluster URL (without https://)
            weaviate_api_key: API key for Weaviate authentication
            openai_api_key: OpenAI API key for vectorization
            collection_name: Name of the Weaviate collection to query
        """
        self.collection_name = collection_name
        self.client: Optional[weaviate.WeaviateClient] = None

        # Store connection params for reconnection if needed
        self._weaviate_url = weaviate_url
        self._weaviate_api_key = weaviate_api_key
        self._openai_api_key = openai_api_key

        logger.info(
            f"🔌 Initializing Weaviate retriever for collection: {collection_name}"
        )
        self._connect()

    def _connect(self) -> None:
        """Establish connection to Weaviate Cloud.

        This handles the connection setup and validates that the required collection
        exists.
        """
        try:
            url = self._weaviate_url.replace("https://", "").replace("http://", "")

            logger.info(f"🔗 Connecting to Weaviate: {url}")

            self.client = weaviate.connect_to_weaviate_cloud(
                cluster_url=url,
                auth_credentials=weaviate.auth.AuthApiKey(self._weaviate_api_key),
                headers={
                    "X-OpenAI-Api-Key": self._openai_api_key  # For query vectorization
                },
            )

            if not self.client.collections.exists(self.collection_name):
                raise ValueError(
                    f"Collection '{self.collection_name}' not found in Weaviate. "
                    "Please trigger the Dagster asset to create and populate it."
                )

            logger.info("✅ Connected to Weaviate successfully")

        except Exception as e:
            logger.error(f"❌ Failed to connect to Weaviate: {e}")
            raise

    def _query_collection(
        self,
        collection_name: str,
        query: str,
        limit: int,
        similarity_threshold: float,
        alpha: float = 0.8,
    ) -> List[RetrievedChunk]:
        """Query a specific Weaviate collection and return filtered chunks.

        Args:
            collection_name: Name of the Weaviate collection
            query: Search query
            limit: Maximum number of results to retrieve
            similarity_threshold: Minimum similarity score to include
            alpha: Hybrid search balance (0=keyword, 1=semantic, default=0.8)

        Returns:
            List of RetrievedChunk objects above threshold, sorted by similarity
        """
        collection = self.client.collections.get(collection_name)

        # Use hybrid search (semantic + keyword)
        # - alpha controls the blend (0=pure keyword, 1=pure semantic)
        # - max_vector_distance gates by the vector component using the provided
        #   similarity_threshold (which historically applied to 1 - distance)
        response = collection.query.hybrid(
            query=query,
            alpha=alpha,
            limit=limit * 2,
            max_vector_distance=(1.0 - similarity_threshold),
            return_metadata=MetadataQuery(score=True),
        )

        chunks: List[RetrievedChunk] = []

        for obj in response.objects:
            score = obj.metadata.score if obj.metadata.score is not None else 0.0
            similarity = float(score)

            # Determine source and create chunk
            if collection_name == "MascotQAPairs":
                chunk = RetrievedChunk(
                    tool="Customer Support",
                    section="Q&A",
                    content=obj.properties.get("qa_pair", ""),
                    similarity=similarity,
                    rank=0,  # Will be assigned later
                    source="qa",
                )
            else:
                chunk = RetrievedChunk(
                    tool=obj.properties.get("tool", "Unknown"),
                    section=obj.properties.get("section", "Unknown"),
                    content=obj.properties.get("content", ""),
                    similarity=similarity,
                    rank=0,  # Will be assigned later
                    source="docs",
                )

            chunks.append(chunk)

        # Sort by similarity (best first)
        chunks.sort(key=lambda x: x.similarity, reverse=True)

        return chunks

    def retrieve(
        self, query: str, top_k: int = 5, similarity_threshold: float = 0.4
    ) -> RAGResult:
        """Retrieve relevant documentation chunks using a dual-collection strategy:

        1. Query BOTH MascotHelpArticles and MascotQAPairs (always)
        2. Get top 10 candidates from each collection (2x top_k)
        3. Combine all results and sort by similarity
        4. Return top_k chunks overall (default: 5)

        This ensures QA pairs always get a chance to compete with docs.

        Args:
            query: User's question or search query
            top_k: Number of final chunks to return (default: 5)
            similarity_threshold: Min similarity score (0-1) to include
                (default: 0.4)

        Returns:
            RAGResult containing retrieved chunks and timing metrics

        Example:
            >>> retriever = WeaviateRetriever(url, api_key, openai_key)
            >>> result = retriever.retrieve("How do I browse templates?", top_k=5)
            >>> # Returns top 5 chunks from both collections combined
        """
        logger.info(f"🔍 Retrieving documentation for query: '{query[:100]}...'")
        start_time = time.time()

        try:
            # Query both collections (get more candidates to ensure good coverage)
            candidate_limit = top_k * 2  # Get 10 candidates from each for top_k=5

            logger.info(
                f"  📚 Querying {self.collection_name} (threshold: {similarity_threshold})"
            )
            docs_chunks = self._query_collection(
                collection_name=self.collection_name,
                query=query,
                limit=candidate_limit,
                similarity_threshold=similarity_threshold,
            )
            logger.info(f"  ✅ Found {len(docs_chunks)} docs above threshold")

            logger.info(
                f"  💬 Querying MascotQAPairs (threshold: {similarity_threshold})"
            )
            qa_chunks = self._query_collection(
                collection_name="MascotQAPairs",
                query=query,
                limit=candidate_limit,
                similarity_threshold=similarity_threshold,
            )
            logger.info(f"  ✅ Found {len(qa_chunks)} QA pairs above threshold")

            # Combine all chunks
            all_chunks = docs_chunks + qa_chunks

            # Sort by similarity (best first) and take top_k
            all_chunks.sort(key=lambda x: x.similarity, reverse=True)
            final_chunks = all_chunks[:top_k]

            # Calculate total retrieval time (both queries)
            retrieval_time_ms = (time.time() - start_time) * 1000

            # Assign final ranks
            for rank, chunk in enumerate(final_chunks, start=1):
                chunk.rank = rank

            # Create result object
            result = RAGResult(
                query=query,
                chunks=final_chunks,
                retrieval_time_ms=retrieval_time_ms,
                total_chunks_found=len(all_chunks),
                chunks_returned=len(final_chunks),
            )

            logger.info(f"✅ {result.get_log_summary()}")

            return result

        except Exception as e:
            logger.error(f"❌ Error retrieving documentation: {e}")
            # Return empty result on error
            return RAGResult(
                query=query,
                chunks=[],
                retrieval_time_ms=(time.time() - start_time) * 1000,
                total_chunks_found=0,
                chunks_returned=0,
            )

    def close(self) -> None:
        """Close the Weaviate connection.

        Call this when shutting down the application to clean up resources.
        """
        if self.client:
            logger.info("🔌 Closing Weaviate connection")
            self.client.close()
            self.client = None

    def __enter__(self) -> "WeaviateRetriever":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Context manager exit - ensures connection is closed."""
        self.close()
