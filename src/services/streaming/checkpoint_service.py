"""
BANK-GRADE: Streaming Checkpoint Service

Provides checkpoint-based streaming with resume capability.
If a stream fails mid-way, clients can resume from the last checkpoint
instead of restarting the entire calculation.

Features:
- Checkpoint storage with TTL (in-memory with Redis-ready interface)
- Resume token generation
- Progress tracking
- Automatic cleanup of expired checkpoints

Architecture:
1. Stream emits checkpoints at key progress milestones
2. Each checkpoint includes a resume_token
3. If stream fails, client can call resume endpoint with token
4. Resume endpoint returns remaining data from checkpoint

Usage:
    service = CheckpointService()
    
    # During streaming
    checkpoint_id = service.create_checkpoint(
        session_id="sess_123",
        stage="dcf_complete",
        progress=50,
        data={"dcf_result": dcf_result}
    )
    
    # On resume
    checkpoint = service.get_checkpoint(resume_token)
    if checkpoint:
        # Resume from checkpoint
        remaining_stages = get_remaining_stages(checkpoint.stage)

Author: Upswitch Engineering Team
Date: January 2026
Status: Production Ready
"""

import time
import uuid
import json
import hashlib
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class StreamingCheckpoint:
    """
    Represents a checkpoint in a streaming valuation.
    
    Attributes:
        checkpoint_id: Unique checkpoint identifier
        session_id: Valuation session ID
        resume_token: Token for resuming from this checkpoint
        stage: Current stage of the calculation (e.g., "dcf_complete", "multiples_complete")
        progress: Progress percentage (0-100)
        data: Checkpoint data (partial results)
        created_at: Timestamp when checkpoint was created
        expires_at: Timestamp when checkpoint expires
        metadata: Additional metadata
    """
    checkpoint_id: str
    session_id: str
    resume_token: str
    stage: str
    progress: int
    data: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)  # 1 hour default
    metadata: Dict[str, Any] = field(default_factory=dict)


# Streaming stages in order of execution
STREAMING_STAGES = [
    "initialized",
    "validation_complete",
    "data_enrichment_complete",
    "dcf_calculation_complete",
    "multiples_calculation_complete",
    "synthesis_complete",
    "report_generation_started",
    "report_section_1",
    "report_section_2",
    "report_section_3",
    "report_complete",
    "finalized",
]


class CheckpointService:
    """
    BANK-GRADE: Service for managing streaming checkpoints.
    
    Provides checkpoint storage, retrieval, and resume functionality.
    Currently uses in-memory storage; ready for Redis migration.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize checkpoint service.
        
        Args:
            ttl_seconds: Time-to-live for checkpoints (default: 1 hour)
        """
        self._checkpoints: Dict[str, StreamingCheckpoint] = {}
        self._session_checkpoints: Dict[str, List[str]] = {}  # session_id -> [checkpoint_ids]
        self._ttl_seconds = ttl_seconds
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
        
        logger.info("CheckpointService initialized", ttl_seconds=ttl_seconds)
    
    def create_checkpoint(
        self,
        session_id: str,
        stage: str,
        progress: int,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StreamingCheckpoint:
        """
        Create a new streaming checkpoint.
        
        Args:
            session_id: Valuation session ID
            stage: Current stage of the calculation
            progress: Progress percentage (0-100)
            data: Checkpoint data (partial results to save)
            metadata: Optional additional metadata
            
        Returns:
            Created StreamingCheckpoint
        """
        # Periodic cleanup
        self._maybe_cleanup()
        
        # Generate unique checkpoint ID
        checkpoint_id = f"ckpt_{uuid.uuid4().hex[:16]}"
        
        # Generate resume token (hash of session + checkpoint for security)
        token_data = f"{session_id}:{checkpoint_id}:{time.time()}"
        resume_token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
        
        # Calculate expiry
        now = time.time()
        expires_at = now + self._ttl_seconds
        
        # Create checkpoint
        checkpoint = StreamingCheckpoint(
            checkpoint_id=checkpoint_id,
            session_id=session_id,
            resume_token=resume_token,
            stage=stage,
            progress=progress,
            data=data,
            created_at=now,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        
        # Store checkpoint
        self._checkpoints[resume_token] = checkpoint
        
        # Track checkpoints by session
        if session_id not in self._session_checkpoints:
            self._session_checkpoints[session_id] = []
        self._session_checkpoints[session_id].append(checkpoint_id)
        
        logger.info(
            "Checkpoint created",
            checkpoint_id=checkpoint_id,
            session_id=session_id[:20] + "..." if len(session_id) > 20 else session_id,
            stage=stage,
            progress=progress,
            expires_in_seconds=self._ttl_seconds,
        )
        
        return checkpoint
    
    def get_checkpoint(self, resume_token: str) -> Optional[StreamingCheckpoint]:
        """
        Retrieve a checkpoint by resume token.
        
        Args:
            resume_token: Resume token from a previous checkpoint
            
        Returns:
            StreamingCheckpoint if found and not expired, None otherwise
        """
        checkpoint = self._checkpoints.get(resume_token)
        
        if not checkpoint:
            logger.debug("Checkpoint not found", resume_token=resume_token[:8] + "...")
            return None
        
        # Check expiry
        if time.time() > checkpoint.expires_at:
            logger.info(
                "Checkpoint expired",
                checkpoint_id=checkpoint.checkpoint_id,
                expired_seconds_ago=time.time() - checkpoint.expires_at,
            )
            # Clean up expired checkpoint
            self._remove_checkpoint(resume_token)
            return None
        
        logger.info(
            "Checkpoint retrieved",
            checkpoint_id=checkpoint.checkpoint_id,
            stage=checkpoint.stage,
            progress=checkpoint.progress,
        )
        
        return checkpoint
    
    def get_latest_checkpoint(self, session_id: str) -> Optional[StreamingCheckpoint]:
        """
        Get the latest checkpoint for a session.
        
        Args:
            session_id: Valuation session ID
            
        Returns:
            Latest StreamingCheckpoint for session, or None
        """
        checkpoint_ids = self._session_checkpoints.get(session_id, [])
        
        if not checkpoint_ids:
            return None
        
        # Find the most recent valid checkpoint
        latest = None
        latest_time = 0
        
        for token, checkpoint in self._checkpoints.items():
            if checkpoint.session_id == session_id:
                if checkpoint.created_at > latest_time and time.time() <= checkpoint.expires_at:
                    latest = checkpoint
                    latest_time = checkpoint.created_at
        
        return latest
    
    def get_remaining_stages(self, current_stage: str) -> List[str]:
        """
        Get remaining stages after the current stage.
        
        Args:
            current_stage: Current stage name
            
        Returns:
            List of remaining stage names
        """
        try:
            current_index = STREAMING_STAGES.index(current_stage)
            return STREAMING_STAGES[current_index + 1:]
        except ValueError:
            logger.warning(f"Unknown stage: {current_stage}")
            return STREAMING_STAGES
    
    def delete_session_checkpoints(self, session_id: str) -> int:
        """
        Delete all checkpoints for a session (cleanup after completion).
        
        Args:
            session_id: Valuation session ID
            
        Returns:
            Number of checkpoints deleted
        """
        tokens_to_remove = []
        
        for token, checkpoint in self._checkpoints.items():
            if checkpoint.session_id == session_id:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            self._remove_checkpoint(token)
        
        if session_id in self._session_checkpoints:
            del self._session_checkpoints[session_id]
        
        logger.info(
            "Session checkpoints deleted",
            session_id=session_id[:20] + "..." if len(session_id) > 20 else session_id,
            count=len(tokens_to_remove),
        )
        
        return len(tokens_to_remove)
    
    def _remove_checkpoint(self, resume_token: str) -> None:
        """Remove a checkpoint by resume token."""
        if resume_token in self._checkpoints:
            del self._checkpoints[resume_token]
    
    def _maybe_cleanup(self) -> None:
        """Periodically clean up expired checkpoints."""
        now = time.time()
        
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        expired_tokens = []
        
        for token, checkpoint in self._checkpoints.items():
            if now > checkpoint.expires_at:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            self._remove_checkpoint(token)
        
        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired checkpoints")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get checkpoint service statistics for monitoring."""
        now = time.time()
        active_count = sum(1 for c in self._checkpoints.values() if now <= c.expires_at)
        
        return {
            "total_checkpoints": len(self._checkpoints),
            "active_checkpoints": active_count,
            "sessions_tracked": len(self._session_checkpoints),
            "ttl_seconds": self._ttl_seconds,
            "last_cleanup": datetime.fromtimestamp(self._last_cleanup).isoformat(),
        }


# Singleton instance
_checkpoint_service: Optional[CheckpointService] = None


def get_checkpoint_service() -> CheckpointService:
    """Get the singleton CheckpointService instance."""
    global _checkpoint_service
    if _checkpoint_service is None:
        _checkpoint_service = CheckpointService()
    return _checkpoint_service
