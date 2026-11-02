"""Fail-closed online check of Titan's current assurance head.

Detached signatures remain valid after a database revocation or supersession.
Consequently ValuationIQ never projects a signed envelope as current authority
without a fresh, authenticated, no-cache response from Titan's authoritative
head/revocation service. Network or contract failure downgrades the report to
``canonical_uncertified``; it never falls back to the offline signature.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.schemas.valuation_assurance_security import (
    ValuationAssuranceEnvelopeV2,
    _parse_timestamp,
    valuation_assurance_hash,
)
from src.api.schemas.valuation_contracts import Sha256Hex, ValuationRunV2
from src.config import Settings, get_settings

CURRENT_STATUS_SCHEMA = "valuation_assurance_current_status.v1"
CURRENT_STATUS_PATH = "/api/v3/internal/valuation-assurance/current"
CURRENT_STATUS_MAX_AGE = timedelta(seconds=5)
CURRENT_STATUS_MAX_CLOCK_SKEW = timedelta(seconds=2)


class ValuationAssuranceStatusUnavailable(ValueError):
    """Titan could not prove that the supplied envelope is the active head."""


class _StrictStatusModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CurrentCertificationManifestBinding(_StrictStatusModel):
    manifest_version: Literal["certification_manifest.v1"]
    manifest_id: str = Field(..., min_length=1)
    manifest_hash: Sha256Hex
    run_schema_version: Literal["valuation_run.v2"]
    engine_version: str = Field(..., min_length=1)
    policy_version: str = Field(..., min_length=1)
    country_code: str = Field(..., pattern=r"^[A-Z]{2}$")
    country_pack_version: str = Field(..., min_length=1)
    calculation_certification_scopes_hash: Sha256Hex


class CurrentValuationAssuranceStatus(_StrictStatusModel):
    schema_version: Literal["valuation_assurance_current_status.v1"]
    request_nonce: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    current: Literal[True]
    checked_at: str
    envelope_id: str = Field(..., min_length=1)
    content_hash: Sha256Hex
    component_hash: Sha256Hex
    company_node_ref_id: str = Field(..., min_length=1)
    audience: Literal["owner", "advisor", "buyer"]
    run_id: str = Field(..., min_length=1)
    run_hash: Sha256Hex
    calculation_hash: Sha256Hex
    observation_set_hash: Sha256Hex
    audience_display_band_hash: Sha256Hex
    publication_authority_id: str = Field(..., min_length=1)
    publication_authority_hash: Sha256Hex
    publication_expires_at: str
    revoked: Literal[False]
    superseded: Literal[False]
    certification_manifest: CurrentCertificationManifestBinding

    @model_validator(mode="after")
    def validate_times(self) -> "CurrentValuationAssuranceStatus":
        _parse_timestamp(self.checked_at, field="current_status.checked_at")
        _parse_timestamp(
            self.publication_expires_at,
            field="current_status.publication_expires_at",
        )
        return self


_CURRENT_AUTHORITY_CONSTRUCTION_TOKEN = object()


@dataclass(frozen=True, init=False)
class CurrentValuationAssuranceAuthority:
    """One request-scoped result of Titan's online current-head decision.

    Report projection APIs accept this authority rather than a raw signed
    envelope.  A detached signature proves origin but cannot prove that the
    envelope has not since been revoked or superseded.
    """

    envelope_id: str
    envelope: ValuationAssuranceEnvelopeV2
    current_status: CurrentValuationAssuranceStatus

    def __init__(
        self,
        *,
        envelope_id: str,
        envelope: ValuationAssuranceEnvelopeV2,
        current_status: CurrentValuationAssuranceStatus,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _CURRENT_AUTHORITY_CONSTRUCTION_TOKEN:
            raise TypeError(
                "CurrentValuationAssuranceAuthority is minted only by Titan's live status verifier"
            )
        object.__setattr__(self, "envelope_id", envelope_id)
        object.__setattr__(self, "envelope", envelope)
        object.__setattr__(self, "current_status", current_status)


def _mint_current_authority(
    *,
    envelope_id: str,
    envelope: ValuationAssuranceEnvelopeV2,
    current_status: CurrentValuationAssuranceStatus,
) -> CurrentValuationAssuranceAuthority:
    return CurrentValuationAssuranceAuthority(
        envelope_id=envelope_id,
        envelope=envelope,
        current_status=current_status,
        _construction_token=_CURRENT_AUTHORITY_CONSTRUCTION_TOKEN,
    )


def _status_request(
    *,
    envelope_id: str,
    envelope: ValuationAssuranceEnvelopeV2,
    request_nonce: str,
) -> dict[str, object]:
    return {
        "schema_version": "valuation_assurance_current_status_request.v1",
        "request_nonce": request_nonce,
        "envelope_id": envelope_id,
        "content_hash": envelope.content_hash,
        "component_hash": envelope.component_hash,
        "company_node_ref_id": envelope.company_node_ref_id,
        "audience": envelope.audience,
        "run_id": envelope.run_id,
        "run_hash": envelope.run_hash,
        "calculation_hash": envelope.calculation_hash,
        "observation_set_hash": envelope.observation_set_hash,
        "audience_display_band_hash": valuation_assurance_hash(
            envelope.audience_display_band.model_dump(mode="python")
        ),
        "certification_manifest_id": envelope.calculation_certification.manifest_id,
        "certification_manifest_hash": envelope.calculation_certification.manifest_hash,
        "calculation_certification_scopes_hash": valuation_assurance_hash(
            envelope.calculation_certification.scopes
        ),
        "publication_authority_id": envelope.publication.authority_id,
        "publication_authority_hash": envelope.publication.authority_hash,
    }


def _bind_current_status(
    status: CurrentValuationAssuranceStatus,
    *,
    envelope_id: str,
    envelope: ValuationAssuranceEnvelopeV2,
    run: ValuationRunV2,
    request_nonce: str,
    now: datetime,
) -> None:
    if status.request_nonce != request_nonce:
        raise ValuationAssuranceStatusUnavailable(
            "Titan valuation-assurance status does not bind this request"
        )
    checked_at = _parse_timestamp(status.checked_at, field="current_status.checked_at")
    if (
        checked_at - now > CURRENT_STATUS_MAX_CLOCK_SKEW
        or now - checked_at > CURRENT_STATUS_MAX_AGE
    ):
        raise ValuationAssuranceStatusUnavailable(
            "Titan valuation-assurance status is future-dated or stale"
        )
    expires_at = _parse_timestamp(
        status.publication_expires_at,
        field="current_status.publication_expires_at",
    )
    if expires_at <= now or expires_at != _parse_timestamp(
        envelope.publication.expires_at,
        field="publication.expires_at",
    ):
        raise ValuationAssuranceStatusUnavailable(
            "Titan valuation-assurance publication expiry changed or elapsed"
        )
    expected = {
        "envelope_id": envelope_id,
        "content_hash": envelope.content_hash,
        "component_hash": envelope.component_hash,
        "company_node_ref_id": envelope.company_node_ref_id,
        "audience": envelope.audience,
        "run_id": envelope.run_id,
        "run_hash": envelope.run_hash,
        "calculation_hash": envelope.calculation_hash,
        "observation_set_hash": envelope.observation_set_hash,
        "audience_display_band_hash": valuation_assurance_hash(
            envelope.audience_display_band.model_dump(mode="python")
        ),
        "publication_authority_id": envelope.publication.authority_id,
        "publication_authority_hash": envelope.publication.authority_hash,
    }
    for field, expected_value in expected.items():
        if getattr(status, field) != expected_value:
            raise ValuationAssuranceStatusUnavailable(
                f"Titan current assurance {field} does not match signed envelope"
            )

    binding = status.certification_manifest
    certification_expected = {
        "manifest_id": envelope.calculation_certification.manifest_id,
        "manifest_hash": envelope.calculation_certification.manifest_hash,
        "run_schema_version": run.schema_version,
        "engine_version": run.engine_version,
        "policy_version": run.policy_version,
        "country_code": run.country_code,
        "country_pack_version": run.country_pack_version,
        "calculation_certification_scopes_hash": valuation_assurance_hash(
            envelope.calculation_certification.scopes
        ),
    }
    for field, expected_value in certification_expected.items():
        if getattr(binding, field) != expected_value:
            raise ValuationAssuranceStatusUnavailable(
                f"Titan certification manifest {field} does not match exact run/dispatch"
            )


async def verify_current_valuation_assurance(
    *,
    envelope_id: str,
    envelope: ValuationAssuranceEnvelopeV2,
    run: ValuationRunV2,
    settings: Settings | None = None,
    now: datetime | None = None,
    client: httpx.AsyncClient | None = None,
) -> CurrentValuationAssuranceAuthority:
    """Mint request-scoped authority only after Titan proves the exact active head."""

    resolved_settings = settings or get_settings()
    base_url = resolved_settings.titan_api_url.rstrip("/")
    token = resolved_settings.titan_valuation_assurance_status_bearer_token.strip()
    if not base_url or not token:
        raise ValuationAssuranceStatusUnavailable(
            "Titan current assurance authority is not configured"
        )
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValuationAssuranceStatusUnavailable(
            "Titan current assurance authority requires an HTTPS origin"
        )
    request_nonce = secrets.token_hex(32)
    request = _status_request(
        envelope_id=envelope_id,
        envelope=envelope,
        request_nonce=request_nonce,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    owned_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(3.0),
        follow_redirects=False,
    )
    try:
        response = await http_client.post(
            f"{base_url}{CURRENT_STATUS_PATH}",
            json=request,
            headers=headers,
        )
        if response.status_code != 200:
            raise ValuationAssuranceStatusUnavailable(
                "Titan did not confirm the current valuation-assurance head"
            )
        if "no-store" not in response.headers.get("cache-control", "").lower():
            raise ValuationAssuranceStatusUnavailable(
                "Titan current valuation-assurance response is not marked no-store"
            )
        try:
            status = CurrentValuationAssuranceStatus.model_validate(response.json())
        except (ValueError, TypeError) as exc:
            raise ValuationAssuranceStatusUnavailable(
                "Titan current valuation-assurance response is invalid"
            ) from exc
        check_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        _bind_current_status(
            status,
            envelope_id=envelope_id,
            envelope=envelope,
            run=run,
            request_nonce=request_nonce,
            now=check_time,
        )
        return _mint_current_authority(
            envelope_id=envelope_id,
            envelope=envelope,
            current_status=status,
        )
    except httpx.HTTPError as exc:
        raise ValuationAssuranceStatusUnavailable(
            "Titan current valuation-assurance authority is unavailable"
        ) from exc
    finally:
        if owned_client:
            await http_client.aclose()
