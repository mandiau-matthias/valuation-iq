"""
ReviewQueueManager

Expert review workflow for Q&A responses flagged by validation pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ReviewPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ReviewQueueItem:
    id: str
    question: str
    answer: str
    source: str
    priority: ReviewPriority = ReviewPriority.MEDIUM
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReviewQueueManager:
    def __init__(self):
        self._queue: List[ReviewQueueItem] = []

    def add_to_queue(self, item: ReviewQueueItem) -> None:
        self._queue.append(item)

    def get_pending(self) -> List[ReviewQueueItem]:
        return [i for i in self._queue if i.status == ReviewStatus.PENDING]

    def get_queue_size(self) -> int:
        return len(self._queue)
