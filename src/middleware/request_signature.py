"""HMAC request-signature verification for service-to-service requests."""

import hashlib
import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request


class SignatureLogger(Protocol):
    """Small logger protocol for structlog and stdlib-compatible loggers."""

    def debug(self, event: str, **kwargs: object) -> object: ...

    def warning(self, event: str, **kwargs: object) -> object: ...

    def error(self, event: str, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class RequestSignatureConfig:
    """Runtime configuration for HMAC request-signature verification."""

    secret: str
    source: str
    fingerprint: str
    max_age_seconds: int


def candidate_signature_payloads(
    request: Request, method: str, timestamp: int, decoded_body: str
) -> list[str]:
    """Return accepted canonical HMAC payloads, most-preferred first."""
    payloads: list[str] = [f"{method}:{timestamp}:{decoded_body}"]

    path = request.url.path
    root_path = str(request.scope.get("root_path") or "")
    slash_variant = path[:-1] if path.endswith("/") and len(path) > 1 else f"{path}/"

    seen: set[str] = set()
    for candidate_path in (path, f"{root_path}{path}" if root_path else "", slash_variant):
        if not candidate_path or candidate_path in seen:
            continue
        seen.add(candidate_path)
        payloads.append(f"{method}:{candidate_path}:{timestamp}:{decoded_body}")

    return payloads


def verify_hmac_request_signature(
    request: Request,
    body: bytes,
    *,
    config: RequestSignatureConfig,
    require_signature: bool = False,
    logger: SignatureLogger,
    now: Callable[[], float] | None = None,
) -> bool:
    """
    Verify request integrity using Titan/ValuationIQ shared-secret HMAC.

    The preferred canonical form is path-independent
    ``METHOD:TIMESTAMP:BODY`` to tolerate proxy path rewrites. Legacy
    path-bound signatures are still accepted for deploy-order compatibility.
    """
    timestamp_str = request.headers.get("x-request-timestamp")
    signature = request.headers.get("x-request-signature")

    if not timestamp_str or not signature:
        if require_signature:
            logger.warning(
                "Service request missing signature headers",
                path=request.url.path,
                method=request.method,
                has_timestamp=bool(timestamp_str),
                has_signature=bool(signature),
            )
            return False
        logger.debug("No request signature headers - skipping verification")
        return True

    try:
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        logger.warning("Invalid request timestamp format", timestamp=timestamp_str)
        return False

    current_time = int((now or time.time)())
    timestamp_age = abs(current_time - timestamp)
    if timestamp_age > config.max_age_seconds:
        logger.warning(
            "Request signature expired",
            timestamp_age_seconds=timestamp_age,
            max_age_seconds=config.max_age_seconds,
        )
        return False

    try:
        decoded_body = body.decode("utf-8")
        method = request.method.upper()
        candidates = candidate_signature_payloads(request, method, timestamp, decoded_body)

        expected_signature = ""
        for payload in candidates:
            candidate_signature = hmac.new(
                config.secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not expected_signature:
                expected_signature = candidate_signature
            if hmac.compare_digest(signature, candidate_signature):
                logger.debug(
                    "Request signature verified successfully",
                    path=request.url.path,
                    timestamp=timestamp,
                )
                return True

        logger.warning(
            "Request signature mismatch",
            path=request.url.path,
            method=method,
            timestamp=timestamp,
            body_len=len(body),
            body_fingerprint=hashlib.sha256(body).hexdigest()[:8],
            candidates_tried=len(candidates),
            signing_secret_source=config.source,
            signing_secret_fingerprint=config.fingerprint,
            received_sig_prefix=signature[:8],
            expected_sig_prefix=expected_signature[:8],
            hint=(
                "Compare signing_secret_fingerprint with Titan's. Equal => the "
                "secret is fine; align the signer's body/timestamp (a proxy "
                "mutated the JSON body, or clock skew). Different => align "
                "SERVICE_SIGNING_SECRET (or JWT_SECRET) across services."
            ),
        )
        return False

    except Exception as exc:
        logger.error(
            "Failed to verify request signature",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return False


__all__ = [
    "RequestSignatureConfig",
    "candidate_signature_payloads",
    "verify_hmac_request_signature",
]
