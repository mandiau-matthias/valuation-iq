"""
ML Embeddings Module

Provides embedding storage, retrieval, and semantic search capabilities
for conversation contexts. Generation has moved to Titan.

Components:
- EmbeddingStore: Redis-backed embedding storage
- SemanticSearch: Vector similarity search
- EmbeddingGenerator: retired generation compatibility shim
"""

from .embedding_store import EmbeddingStore, get_embedding_store
from .semantic_search import SemanticSearch, get_semantic_search
from .embedding_generator import EmbeddingGenerator, get_embedding_generator

__all__ = [
    'EmbeddingStore',
    'get_embedding_store',
    'SemanticSearch', 
    'get_semantic_search',
    'EmbeddingGenerator',
    'get_embedding_generator'
]
