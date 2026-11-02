"""
Privacy module - sanitization and audit for Titan-boundary-safe data handling.

Provides PrivacyGuard and PrivacyGuardRefactored for:
- sanitize_for_ai: Legacy helper that strips private data before handoff
- audit_ai_request: Legacy helper that validates public-only context
- create_safe_context: Build public-only context for deterministic market notes
"""

from src.services.privacy.privacy_guard import PrivacyGuard
from src.services.privacy.security.privacy_guard import PrivacyGuardRefactored

__all__ = ["PrivacyGuard", "PrivacyGuardRefactored"]
