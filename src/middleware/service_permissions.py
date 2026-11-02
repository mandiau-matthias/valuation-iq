"""
Service-to-service permission contract for ValuationIQ.

Titan calls ValuationIQ with short-lived service JWTs. Keeping service IDs,
allowed endpoint actions, and path-to-action mapping in this small module makes
the internal trust boundary auditable without reading the full user auth stack.
"""

import os
from typing import Dict, List, Optional

SERVICE_ACCOUNTS: Dict[str, List[str]] = {
    "titan-api-service": [
        "calculate",
        "generate-report",
        "stream",
        "pdf",
        "conversation",
        "health",
        "quick",
        "buyer-ready-package",
        "acquisition-shortlist-render",
        "acquisition-scenarios",
        "imported-ledger",
        "scan-lease-ifrs16",
        "scan-owner-benefits",
        "scan-related-party",
        "scan-sde-flags",
        "validate",
    ],
}

SERVICE_TOKEN_MAX_AGE_SECONDS = 300
SERVICE_TOKEN_CLOCK_SKEW_SECONDS = 30


def _int_env(name: str, default: int) -> int:
    """Read a positive int from the environment, falling back on any bad value."""
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


# Max age (each direction) of a request-signature timestamp before it is
# rejected as a replay. Env-overridable so ops can widen the window during a
# clock-skew incident WITHOUT a redeploy; defaults to 5 minutes.
REQUEST_SIGNATURE_MAX_AGE_SECONDS = _int_env("REQUEST_SIGNATURE_MAX_AGE_SECONDS", 300)


class ServiceAccount:
    """
    Authenticated service identity.

    Attributes:
        id: Unique service identifier, for example "titan-api-service".
        role: Always "service" for service accounts.
        allowed_actions: Endpoint action identifiers this service can access.
        issued_at: Token issuance timestamp used for replay protection.
    """

    def __init__(
        self,
        id: str,
        allowed_actions: List[str],
        issued_at: Optional[int] = None,
    ):
        self.id = id
        self.role = "service"
        self.allowed_actions = allowed_actions
        self.issued_at = issued_at

    def can_access(self, action: str) -> bool:
        """Check whether this service account can access the given action."""
        return action in self.allowed_actions


def _path_segments(path: str) -> List[str]:
    """Return normalized path segments without query strings or empty separators."""
    path_without_query = path.split("?", 1)[0]
    return [segment.lower() for segment in path_without_query.split("/") if segment]


def _has_adjacent_segments(segments: List[str], first: str, second: str) -> bool:
    return any(
        current == first and next_segment == second
        for current, next_segment in zip(segments, segments[1:])
    )


def extract_action_from_path(path: str) -> str:
    """
    Map a request path to a service permission action.

    Examples:
        /api/v1/valuation/calculate -> calculate
        /api/v2/stateless/generate-report -> generate-report
        /api/v1/normalization/scan-sde-flags -> scan-sde-flags
        /api/v1/valuation/pdf/report-id -> pdf
        /api/v1/accounting-analysis/imported-ledger -> imported-ledger
        /health -> health
    """
    segments = _path_segments(path)

    if segments == ["api", "v1", "acquisition", "scenarios"]:
        return "acquisition-scenarios"

    if "health" in segments:
        return "health"

    if _has_adjacent_segments(segments, "accounting-analysis", "imported-ledger"):
        return "imported-ledger"

    if segments == ["api", "v1", "acquisition-shortlists", "render"]:
        return "acquisition-shortlist-render"

    if segments == ["api", "v2", "stateless", "calculate-partial"]:
        return "calculate"
    if segments == ["api", "v2", "stateless", "generate-assessment-report"]:
        return "generate-report"
    if segments == ["api", "v2", "stateless", "generate-partial-report"]:
        return "generate-report"

    if "stateless" in segments:
        stateless_index = segments.index("stateless")
        stateless_segments = segments[stateless_index + 1 :]
        if stateless_segments:
            return stateless_segments[0]

    if "normalization" in segments:
        normalization_index = segments.index("normalization")
        normalization_segments = segments[normalization_index + 1 :]
        if normalization_segments:
            return normalization_segments[0]

    if "buyer-ready-package" in segments:
        return "buyer-ready-package"

    if "reports" in segments:
        reports_index = segments.index("reports")
        reports_segments = segments[reports_index + 1 :]
        if reports_segments and reports_segments[0] == "pdf":
            return "pdf"
        return "generate-report"

    if "valuation" in segments:
        valuation_index = segments.index("valuation")
        valuation_segments = set(segments[valuation_index + 1 :])
        for action in ("calculate", "stream", "pdf", "quick"):
            if action in valuation_segments:
                return action

    if "conversation" in segments:
        return "conversation"

    if segments:
        return segments[-1]

    return "unknown"


def get_service_allowed_actions(service_id: str) -> List[str] | None:
    """Return the configured permissions for a known service identity."""
    return SERVICE_ACCOUNTS.get(service_id)


def validate_service_token_issued_at(issued_at: object, now: int) -> int:
    """
    Validate service-token issuance time and return it as an integer timestamp.

    Service tokens are replay-sensitive internal credentials. Missing, malformed,
    stale, or far-future ``iat`` claims fail closed so every accepted service
    token is short-lived by construction.
    """
    if isinstance(issued_at, bool) or not isinstance(issued_at, (int, float)):
        raise ValueError("missing_or_invalid_iat")

    issued_at_int = int(issued_at)
    token_age = now - issued_at_int

    if token_age < -SERVICE_TOKEN_CLOCK_SKEW_SECONDS:
        raise ValueError("iat_in_future")

    if token_age > SERVICE_TOKEN_MAX_AGE_SECONDS:
        raise ValueError("iat_expired")

    return issued_at_int
