from src.utils.exceptions import CacheError, DataValidationError, DatabaseError, ValuationRangeError

"""
Semantic Search for Conversation Contexts

Provides semantic search capabilities using vector embeddings
to find similar conversations, detect duplicates, and enable
deterministic recommendations.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError

from src.utils.logging import get_logger
from src.config import settings
from src.database.redis_client import get_redis_client
from .embedding_store import get_embedding_store
from .embedding_generator import get_embedding_generator
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class SemanticSearch:
    """
    Semantic search engine for conversation contexts

    Features:
    - Find similar conversations across sessions
    - Detect duplicate questions
    - Recommend based on semantic similarity
    - Support clustering analysis
    - Cross-session intelligence
    """

    def __init__(self):
        """Initialize semantic search"""
        self.embedding_store = get_embedding_store()
        self.embedding_generator = get_embedding_generator()
        self.redis_client: Optional[redis.Redis] = None

        # Search configuration
        self.default_similarity_threshold = Decimal('0.7')
        self.max_results = 10
        self.cache_ttl = 3600  # 1 hour

        logger.info("SemanticSearch initialized", 
                   threshold=self.default_similarity_threshold,
                   max_results=self.max_results)

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client for search caching"""
        if not self.redis_client:
            try:
                self.redis_client = await get_redis_client()
            except DatabaseError as e:
                logger.error(f"Failed to get Redis client: {e}")
                return None
        return self.redis_client

    async def find_similar_conversations(
        self, 
        query_text: str, 
        exclude_session_id: Optional[str] = None,
        limit: int = 5,
        threshold: Decimal = Decimal('0.7')
    ) -> List[Dict[str, Any]]:
        """
        Find conversations similar to query text

        Args:
            query_text: Text to search for
            exclude_session_id: Session to exclude from results
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of similar conversation results
        """
        try:
            # Generate embedding for query
            query_embedding = await self.embedding_generator.generate_embedding(query_text)
            if not query_embedding:
                logger.warning("Failed to generate query embedding")
                return []

            # Search across all sessions
            similar_conversations = await self._search_across_sessions(
                query_embedding, 
                exclude_session_id, 
                limit, 
                threshold
            )

            logger.debug("Similar conversations found", 
                        query_length=len(query_text),
                        results_count=len(similar_conversations),
                        threshold=threshold)

            return similar_conversations

        except DatabaseError as e:
            logger.error(f"Error finding similar conversations: {e}")
            return []

    async def _search_across_sessions(
        self, 
        query_embedding: List[Decimal],
        exclude_session_id: Optional[str] = None,
        limit: int = 5,
        threshold: Decimal = Decimal('0.7')
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings across all sessions"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return []

            # Get all session embedding keys
            pattern = "embeddings:session:*:all"
            session_keys = await redis_client.keys(pattern)

            all_similarities = []

            for session_key in session_keys:
                # Extract session ID from key
                session_id = session_key.decode().split(':')[2]

                # Skip excluded session
                if exclude_session_id and session_id == exclude_session_id:
                    continue

                # Get embeddings for this session
                embeddings = await self.embedding_store.get_session_embeddings(session_id)

                # Calculate similarities
                for embedding_data in embeddings:
                    embedding_vector = np.array(embedding_data["embedding"])
                    query_vector = np.array(query_embedding)

                    similarity = self._cosine_similarity(query_vector, embedding_vector)

                    if similarity >= threshold:
                        all_similarities.append({
                            "session_id": session_id,
                            "message_id": embedding_data["message_id"],
                            "similarity": to_decimal(similarity),
                            "metadata": embedding_data.get("metadata", {}),
                            "created_at": embedding_data.get("created_at")
                        })

            # Sort by similarity and limit results
            all_similarities.sort(key=lambda x: x["similarity"], reverse=True)
            results = all_similarities[:limit]

            return results

        except ValuationEngineError as e:
            logger.error(f"Error searching across sessions: {e}")
            return []

    async def detect_duplicate_questions(
        self, 
        question_text: str, 
        session_id: str,
        threshold: Decimal = Decimal('0.8')
    ) -> List[Dict[str, Any]]:
        """
        Detect if a question has been asked before in similar form

        Args:
            question_text: Question to check for duplicates
            session_id: Current session ID
            threshold: Similarity threshold for duplicates

        Returns:
            List of potential duplicate questions
        """
        try:
            # Find similar conversations (excluding current session)
            similar_conversations = await self.find_similar_conversations(
                question_text,
                exclude_session_id=session_id,
                limit=3,
                threshold=threshold
            )

            # Filter for high similarity (potential duplicates)
            duplicates = [
                conv for conv in similar_conversations 
                if conv["similarity"] >= threshold
            ]

            logger.debug("Duplicate detection completed", 
                        question_length=len(question_text),
                        duplicates_found=len(duplicates),
                        threshold=threshold)

            return duplicates

        except ValuationEngineError as e:
            logger.error(f"Error detecting duplicate questions: {e}")
            return []

    async def get_conversation_recommendations(
        self, 
        session_id: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get conversation recommendations based on current session

        Args:
            session_id: Current session ID
            limit: Maximum number of recommendations

        Returns:
            List of conversation recommendations
        """
        try:
            # Get current session embeddings
            session_embeddings = await self.embedding_store.get_session_embeddings(session_id)

            if not session_embeddings:
                logger.debug("No embeddings found for recommendations", session_id=session_id)
                return []

            # Use the most recent embedding as query
            latest_embedding = session_embeddings[-1]["embedding"]

            # Find similar conversations
            recommendations = await self._search_across_sessions(
                latest_embedding,
                exclude_session_id=session_id,
                limit=limit,
                threshold=Decimal('0.6')  # Lower threshold for recommendations
            )

            # Add recommendation metadata
            for rec in recommendations:
                rec["recommendation_type"] = "similar_conversation"
                rec["confidence"] = rec["similarity"]

            logger.debug("Conversation recommendations generated", 
                        session_id=session_id,
                        recommendations_count=len(recommendations))

            return recommendations

        except ValuationEngineError as e:
            logger.error(f"Error generating conversation recommendations: {e}")
            return []

    async def cluster_conversations(
        self, 
        session_ids: List[str],
        num_clusters: int = 3
    ) -> Dict[str, List[str]]:
        """
        Cluster conversations by semantic similarity

        Args:
            session_ids: List of session IDs to cluster
            num_clusters: Number of clusters to create

        Returns:
            Dictionary mapping cluster_id to list of session_ids
        """
        try:
            # Collect all embeddings
            all_embeddings = []
            session_embedding_map = {}

            for session_id in session_ids:
                embeddings = await self.embedding_store.get_session_embeddings(session_id)
                if embeddings:
                    # Use average embedding for the session
                    session_embedding = np.mean([emb["embedding"] for emb in embeddings], axis=0)
                    all_embeddings.append(session_embedding)
                    session_embedding_map[len(all_embeddings) - 1] = session_id

            if len(all_embeddings) < num_clusters:
                logger.warning("Not enough sessions for clustering", 
                              sessions=len(all_embeddings),
                              requested_clusters=num_clusters)
                return {"cluster_0": session_ids}

            # Simple K-means clustering
            clusters = self._simple_kmeans(all_embeddings, num_clusters)

            # Map sessions to clusters
            result_clusters = {}
            for cluster_id, indices in clusters.items():
                cluster_sessions = [session_embedding_map[i] for i in indices]
                result_clusters[f"cluster_{cluster_id}"] = cluster_sessions

            logger.debug("Conversation clustering completed", 
                        total_sessions=len(session_ids),
                        clusters_created=len(result_clusters))

            return result_clusters

        except ValuationRangeError as e:
            logger.error(f"Error clustering conversations: {e}")
            return {"cluster_0": session_ids}

    def _simple_kmeans(self, embeddings: List[np.ndarray], k: int) -> Dict[int, List[int]]:
        """Simple K-means clustering implementation"""
        try:
            if len(embeddings) <= k:
                return {i: [i] for i in range(len(embeddings))}

            # Initialize centroids randomly
            centroids = embeddings[:k].copy()

            # Simple iteration (not optimized)
            for _ in range(10):  # Max 10 iterations
                clusters = {i: [] for i in range(k)}

                # Assign each embedding to closest centroid
                for i, embedding in enumerate(embeddings):
                    distances = [self._cosine_similarity(embedding, centroid) for centroid in centroids]
                    closest_cluster = distances.index(max(distances))
                    clusters[closest_cluster].append(i)

                # Update centroids
                for cluster_id, indices in clusters.items():
                    if indices:
                        cluster_embeddings = [embeddings[i] for i in indices]
                        centroids[cluster_id] = np.mean(cluster_embeddings, axis=0)

            return clusters

        except ValuationRangeError as e:
            logger.error(f"Error in K-means clustering: {e}")
            return {0: list(range(len(embeddings)))}

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> Decimal:
        """Calculate cosine similarity between two vectors"""
        try:
            # Normalize vectors
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return Decimal('0.0')

            # Calculate cosine similarity
            similarity = np.dot(vec1, vec2) / (norm1 * norm2)
            return to_decimal(similarity)

        except DataValidationError as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return Decimal('0.0')

    async def health_check(self) -> Dict[str, Any]:
        """Check semantic search health"""
        try:
            # Check embedding store
            embedding_store_health = await self.embedding_store.health_check()

            # Check embedding generator
            generator_health = await self.embedding_generator.health_check()

            return {
                "status": "healthy" if embedding_store_health["status"] == "healthy" and generator_health["status"] == "healthy" else "unhealthy",
                "embedding_store": embedding_store_health,
                "embedding_generator": generator_health,
                "similarity_threshold": self.default_similarity_threshold,
                "max_results": self.max_results
            }

        except DataValidationError as e:
            logger.error(f"Semantic search health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Get semantic search statistics"""
        try:
            embedding_store_stats = await self.embedding_store.get_stats()
            generator_stats = await self.embedding_generator.get_stats()

            return {
                "embedding_store": embedding_store_stats,
                "embedding_generator": generator_stats,
                "similarity_threshold": self.default_similarity_threshold,
                "max_results": self.max_results,
                "cache_ttl": self.cache_ttl
            }

        except CacheError as e:
            logger.error(f"Error getting semantic search stats: {e}")
            return {"error": str(e)}


# Global instance
_semantic_search: Optional[SemanticSearch] = None


def get_semantic_search() -> SemanticSearch:
    """Get global semantic search instance"""
    global _semantic_search
    if _semantic_search is None:
        _semantic_search = SemanticSearch()
    return _semantic_search
