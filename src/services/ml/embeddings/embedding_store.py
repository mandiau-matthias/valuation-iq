"""
Embedding Store for Redis-backed Vector Storage

Provides efficient storage and retrieval of conversation embeddings
with support for similarity search and caching.
"""

import json
import hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from src.utils.logging import get_logger
from src.config import settings
from src.database.redis_client import get_redis_client
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class EmbeddingStore:
    """
    Redis-backed embedding storage with similarity search capabilities

    Features:
    - Store conversation embeddings in Redis
    - Vector similarity search
    - Embedding caching for precomputed vectors
    - TTL management
    - Batch operations
    """

    def __init__(self):
        """Initialize embedding store"""
        self.redis_client: Optional[redis.Redis] = None
        self.key_prefix = "embeddings"
        self.similarity_index_prefix = "similarity"
        self.cache_ttl = settings.context_guest_ttl  # Use same TTL as context

        # Legacy 1536-dimensional vectors remain supported for compatibility.
        self.embedding_dim = 1536

        logger.info("EmbeddingStore initialized", 
                   cache_ttl=self.cache_ttl,
                   embedding_dim=self.embedding_dim)

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client for embeddings (DB 0)"""
        if not self.redis_client:
            try:
                self.redis_client = await get_redis_client()
            except Exception as e:
                logger.error(f"Failed to get Redis client: {e}")
                return None
        return self.redis_client

    def _get_embedding_key(self, session_id: str, message_id: str) -> str:
        """Generate Redis key for embedding"""
        return f"{self.key_prefix}:session:{session_id}:message:{message_id}"

    def _get_session_embeddings_key(self, session_id: str) -> str:
        """Generate Redis key for session embeddings list"""
        return f"{self.key_prefix}:session:{session_id}:all"

    def _get_similarity_key(self, session_id: str) -> str:
        """Generate Redis key for similarity index"""
        return f"{self.similarity_index_prefix}:session:{session_id}"

    async def store_embedding(
        self, 
        session_id: str, 
        message_id: str, 
        embedding: List[Decimal],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store embedding for a specific message

        Args:
            session_id: Session identifier
            message_id: Message identifier
            embedding: Vector embedding (1536 dimensions)
            metadata: Optional metadata (timestamp, confidence, etc.)

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for embedding storage")
                return False

            # Validate embedding dimensions
            if len(embedding) != self.embedding_dim:
                logger.error(f"Invalid embedding dimension: {len(embedding)}, expected {self.embedding_dim}")
                return False

            # Prepare embedding data
            embedding_data = {
                "embedding": embedding,
                "session_id": session_id,
                "message_id": message_id,
                "dimensions": self.embedding_dim,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            # Store individual embedding
            key = self._get_embedding_key(session_id, message_id)
            await redis_client.setex(
                key, 
                self.cache_ttl, 
                json.dumps(embedding_data)
            )

            # Add to session embeddings list
            session_key = self._get_session_embeddings_key(session_id)
            await redis_client.sadd(session_key, message_id)
            await redis_client.expire(session_key, self.cache_ttl)

            logger.debug("Embedding stored", 
                        session_id=session_id, 
                        message_id=message_id,
                        dimensions=len(embedding))

            return True

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error storing embedding: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing embedding: {e}")
            return False

    async def get_embedding(
        self, 
        session_id: str, 
        message_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve embedding for a specific message

        Args:
            session_id: Session identifier
            message_id: Message identifier

        Returns:
            Embedding data with metadata or None if not found
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for embedding retrieval")
                return None

            key = self._get_embedding_key(session_id, message_id)
            data = await redis_client.get(key)

            if not data:
                logger.debug("Embedding not found", session_id=session_id, message_id=message_id)
                return None

            embedding_data = json.loads(data)
            logger.debug("Embedding retrieved", 
                        session_id=session_id, 
                        message_id=message_id)

            return embedding_data

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error retrieving embedding: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving embedding: {e}")
            return None

    async def get_session_embeddings(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all embeddings for a session

        Args:
            session_id: Session identifier

        Returns:
            List of embedding data for the session
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for session embeddings")
                return []

            # Get all message IDs for the session
            session_key = self._get_session_embeddings_key(session_id)
            message_ids = await redis_client.smembers(session_key)

            if not message_ids:
                logger.debug("No embeddings found for session", session_id=session_id)
                return []

            # Retrieve embeddings for each message
            embeddings = []
            for message_id in message_ids:
                message_id_str = message_id.decode() if isinstance(message_id, bytes) else message_id
                embedding_data = await self.get_embedding(session_id, message_id_str)
                if embedding_data:
                    embeddings.append(embedding_data)

            logger.debug("Session embeddings retrieved", 
                        session_id=session_id, 
                        count=len(embeddings))

            return embeddings

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error retrieving session embeddings: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving session embeddings: {e}")
            return []

    async def find_similar_embeddings(
        self, 
        query_embedding: List[Decimal], 
        session_id: str,
        limit: int = 5,
        threshold: Decimal = Decimal('0.7')
    ) -> List[Tuple[str, float]]:
        """
        Find similar embeddings within a session using cosine similarity

        Args:
            query_embedding: Query vector
            session_id: Session to search within
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of (message_id, similarity_score) tuples
        """
        try:
            # Get all embeddings for the session
            embeddings = await self.get_session_embeddings(session_id)

            if not embeddings:
                logger.debug("No embeddings found for similarity search", session_id=session_id)
                return []

            # Calculate similarities
            similarities = []
            query_vector = np.array(query_embedding)

            for embedding_data in embeddings:
                embedding_vector = np.array(embedding_data["embedding"])

                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_vector, embedding_vector)

                if similarity >= threshold:
                    similarities.append((
                        embedding_data["message_id"], 
                        to_decimal(similarity)
                    ))

            # Sort by similarity and limit results
            similarities.sort(key=lambda x: x[1], reverse=True)
            results = similarities[:limit]

            logger.debug("Similarity search completed", 
                        session_id=session_id,
                        query_dimensions=len(query_embedding),
                        results_count=len(results),
                        threshold=threshold)

            return results

        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            return []

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

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return Decimal('0.0')

    async def delete_session_embeddings(self, session_id: str) -> bool:
        """
        Delete all embeddings for a session

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for embedding deletion")
                return False

            # Get all message IDs for the session
            session_key = self._get_session_embeddings_key(session_id)
            message_ids = await redis_client.smembers(session_key)

            # Delete individual embeddings
            keys_to_delete = []
            for message_id in message_ids:
                message_id_str = message_id.decode() if isinstance(message_id, bytes) else message_id
                key = self._get_embedding_key(session_id, message_id_str)
                keys_to_delete.append(key)

            # Delete all keys at once
            if keys_to_delete:
                await redis_client.delete(*keys_to_delete)

            # Delete session key
            await redis_client.delete(session_key)

            logger.debug("Session embeddings deleted", 
                        session_id=session_id, 
                        count=len(keys_to_delete))

            return True

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error deleting embeddings: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting embeddings: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check embedding store health"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {
                    "status": "unhealthy",
                    "error": "Redis client unavailable"
                }

            # Test Redis connection
            await redis_client.ping()

            # Get basic stats
            info = await redis_client.info()

            return {
                "status": "healthy",
                "redis_connected": True,
                "memory_usage": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "embedding_dimensions": self.embedding_dim,
                "cache_ttl": self.cache_ttl
            }

        except Exception as e:
            logger.error(f"Embedding store health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Get embedding store statistics"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {"error": "Redis client unavailable"}

            # Count embedding keys
            pattern = f"{self.key_prefix}:session:*:message:*"
            keys = await redis_client.keys(pattern)
            embedding_count = len(keys)

            # Count session keys
            session_pattern = f"{self.key_prefix}:session:*:all"
            session_keys = await redis_client.keys(session_pattern)
            session_count = len(session_keys)

            return {
                "total_embeddings": embedding_count,
                "total_sessions": session_count,
                "embedding_dimensions": self.embedding_dim,
                "cache_ttl": self.cache_ttl,
                "redis_memory_usage": await redis_client.memory_usage()
            }

        except Exception as e:
            logger.error(f"Error getting embedding stats: {e}")
            return {"error": str(e)}


# Global instance
_embedding_store: Optional[EmbeddingStore] = None


def get_embedding_store() -> EmbeddingStore:
    """Get global embedding store instance"""
    global _embedding_store
    if _embedding_store is None:
        _embedding_store = EmbeddingStore()
    return _embedding_store
