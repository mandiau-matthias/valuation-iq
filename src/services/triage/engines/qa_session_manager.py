"""
QA Session Manager

Multi-turn Q&A session management with depth limiting and progressive nudging.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional


class QASessionState(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    LIMIT_APPROACHING = "limit_approaching"
    LIMIT_REACHED = "limit_reached"


class NudgingStrategy(str, Enum):
    GENTLE = "gentle"
    MODERATE = "moderate"
    FIRM = "firm"


@dataclass
class QASession:
    session_id: str
    current_field: Optional[str] = None
    state: QASessionState = QASessionState.INACTIVE
    qa_depth: int = 0
    max_depth: int = 3
    questions: List[str] = field(default_factory=list)
    answers: List[str] = field(default_factory=list)
    nudging_strategy: NudgingStrategy = NudgingStrategy.GENTLE
    started_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None

    def can_ask_more(self) -> bool:
        return self.qa_depth < self.max_depth

    def is_active(self) -> bool:
        return self.state in (QASessionState.ACTIVE, QASessionState.LIMIT_APPROACHING, QASessionState.LIMIT_REACHED)

    def get_remaining_questions(self) -> int:
        return max(0, self.max_depth - self.qa_depth)


class QASessionManager:
    def __init__(self, max_depth: int = 3, session_timeout_minutes: int = 30):
        self.max_depth = max_depth
        self.session_timeout_minutes = session_timeout_minutes
        self._sessions: Dict[str, QASession] = {}

    def enter_qa_mode(self, session_id: str, field: str) -> QASession:
        session = QASession(
            session_id=session_id,
            current_field=field,
            state=QASessionState.ACTIVE,
            qa_depth=0,
            max_depth=self.max_depth,
            questions=[],
            answers=[],
            nudging_strategy=NudgingStrategy.GENTLE,
            started_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> QASession:
        session = self._sessions.get(session_id)
        if session is None:
            session = QASession(
                session_id=session_id,
                state=QASessionState.INACTIVE,
            )
            self._sessions[session_id] = session
            return session

        if session.last_activity and session.state != QASessionState.INACTIVE:
            elapsed = datetime.utcnow() - session.last_activity
            if elapsed > timedelta(minutes=self.session_timeout_minutes):
                session.state = QASessionState.INACTIVE
                session.qa_depth = 0
                session.questions = []
                session.answers = []
        return session

    def exit_qa_mode(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.state = QASessionState.INACTIVE
        session.qa_depth = 0
        session.questions = []
        session.answers = []
        session.current_field = None
        return True

    def track_qa_turn(self, session_id: str, question: str, answer: str) -> QASession:
        session = self._sessions.get(session_id)
        if session is None:
            session = self.enter_qa_mode(session_id, "unknown")

        session.questions.append(question)
        session.answers.append(answer)
        session.qa_depth += 1
        session.last_activity = datetime.utcnow()

        if session.qa_depth >= session.max_depth:
            session.state = QASessionState.LIMIT_REACHED
            session.nudging_strategy = NudgingStrategy.FIRM
        elif session.qa_depth >= session.max_depth - 1:
            session.state = QASessionState.LIMIT_APPROACHING
            session.nudging_strategy = NudgingStrategy.FIRM
        else:
            session.state = QASessionState.ACTIVE
            session.nudging_strategy = NudgingStrategy.MODERATE

        return session

        return session

    def should_block_question(self, session: QASession) -> bool:
        return session.state == QASessionState.LIMIT_REACHED

    def get_block_message(self, session: QASession) -> str:
        return (
            f"We've already answered {session.qa_depth} questions about {session.current_field}. "
            f"Let's continue with the valuation process."
        )

    def get_nudge_message(self, session: QASession) -> str:
        field = session.current_field or "the current topic"
        remaining = session.get_remaining_questions()

        if session.state == QASessionState.LIMIT_REACHED:
            return f"We've covered {field} thoroughly. Let's complete the valuation and finish up."
        elif session.state == QASessionState.LIMIT_APPROACHING:
            return f"You have {remaining} question(s) left. We can continue, then we'll go back to the valuation."
        elif session.nudging_strategy == NudgingStrategy.MODERATE:
            return f"We can continue discussing {field}. Let me know when you're ready to proceed with {field}."
        else:
            return f"Feel free to continue asking about {field}, or let me know when you're ready to proceed."

    def get_stats(self) -> Dict:
        total = len(self._sessions)
        active = sum(1 for s in self._sessions.values() if s.is_active())
        depths = [s.qa_depth for s in self._sessions.values() if s.qa_depth > 0]
        avg_depth = sum(depths) / len(depths) if depths else 0.0
        return {
            "total_sessions": total,
            "active_sessions": active,
            "avg_qa_depth": avg_depth,
            "max_allowed_depth": self.max_depth,
        }

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> None:
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_remove = [
            sid for sid, s in self._sessions.items()
            if s.last_activity and s.last_activity < cutoff
        ]
        for sid in to_remove:
            del self._sessions[sid]
