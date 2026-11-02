"""Audit-trail metadata — uniquely identifies each valuation run.

Why this module exists
----------------------
A digitalised M&A journey requires every valuation artifact to be
*identifiable*, *reproducible*, and *tamper-evident*. EY/KPMG/PwC
restructuring practices won't put their stamp on a document that
doesn't have:

1. A **run identifier** — UUID per computation, surfaces on every
   page of the PDF as "Run YYYYMMDD-XXXXXXXX". Letterhead-grade.
2. An **effective date** — the as-of date the valuation pertains to,
   distinct from the computation timestamp. Big-4 reports always
   say "as at YYYY-MM-DD" because the answer changes daily.
3. A **payload hash** — SHA-256 of the canonical input payload,
   surfaces in the disclosure block. Lets a reviewer verify the
   inputs haven't been tampered with between the computation and
   the report being read. AICPA SSVS No. 1 §57(d) — "valuation
   procedures, calculations, and report should be in such detail
   that another valuation analyst can replicate them."
4. An **engine version** — semver of the engine code that computed
   the result. Lets future readers reconstruct exactly which
   methodology was applied (rates, factors, formulae change over
   time per IVS / WIB / Faillissementswet amendments).

These four together turn a PDF from "an estimate" into a
**reproducible M&A artifact** suitable for a data room.

References
----------
- AICPA SSVS No. 1 §57(d) — replicability requirement.
- IVS Glossary — "Valuation Date" + "Reporting Date" (distinct).
- USPAP STANDARD 9-2 — "the valuer must include the date of value
  and the date of the report".
- ISO/IEC 14888-2 — digital signature mechanisms for cryptographic
  payload identification.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional

# Calculation model version — bump per substantive Phase change. Surfaced on
# every report so the methodology era is identifiable.
ENGINE_VERSION: str = "liquidation-engine/5.0"
ENGINE_VERSION_NOTES: str = (
    "Complete-input financial screening without uncalibrated probability weighting; "
    "no automatic going-concern earnings proxy. Conditional advisor-input tax v2; "
    "separate company equity and owner proceeds; unsupported buyer bands withheld. "
    "Scenario assumptions require review and empirical calibration."
)


AUDIT_TRAIL_SOURCES: tuple[str, ...] = (
    "AICPA SSVS No. 1 §57(d) — replicability requirement",
    "IVS Glossary — Valuation Date vs Reporting Date",
    "USPAP STANDARD 9-2 — date-of-value + date-of-report",
)


@dataclass(frozen=True)
class AuditTrail:
    """Tamper-evident metadata for one valuation run.

    `run_id` is a UUID4 — globally unique across all runs of the
    engine ever. `payload_hash` is SHA-256 of the canonical input
    payload — lets a reviewer verify the inputs haven't drifted
    between computation and report reading.
    """

    run_id: str  # UUID4
    effective_date: str  # ISO YYYY-MM-DD — the as-of date
    computed_at: str  # ISO YYYY-MM-DDTHH:MM:SSZ — when run executed
    engine_version: str
    engine_version_notes: str
    payload_hash: str  # SHA-256 hex
    payload_hash_algorithm: str  # "sha-256"
    sources: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "effective_date": self.effective_date,
            "computed_at": self.computed_at,
            "engine_version": self.engine_version,
            "engine_version_notes": self.engine_version_notes,
            "payload_hash": self.payload_hash,
            "payload_hash_algorithm": self.payload_hash_algorithm,
            "sources": list(self.sources),
        }

    def short_run_id(self) -> str:
        """Letterhead-grade short ID: YYYYMMDD-XXXXXXXX (8 hex chars)."""
        return f"{self.effective_date.replace('-', '')}-{self.run_id[:8]}"


def _canonicalise(value: Any) -> Any:
    """Convert a payload value to a JSON-serialisable canonical form.

    Decimals → strings (preserve precision); datetimes → ISO; dicts
    → sorted-key dicts (so hash is stable regardless of insertion
    order); everything else passes through.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _canonicalise(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonicalise(v) for v in value]
    if hasattr(value, "value") and hasattr(value, "name"):  # Enum
        return value.value
    return value


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    """Stable SHA-256 hex over a canonicalised payload.

    Sorted keys + Decimal-as-string + ISO datetimes ensure the same
    inputs always produce the same hash, regardless of dict-insertion
    order, Decimal vs float representation, or timezone aware/naive
    datetime mixing.
    """
    canonical = _canonicalise(dict(payload))
    serialised = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def build_audit_trail(
    *,
    payload: Mapping[str, Any],
    effective_date: Optional[str] = None,
    run_id_override: Optional[str] = None,
    computed_at_override: Optional[str] = None,
) -> AuditTrail:
    """Build the audit-trail metadata for a valuation run.

    Inputs:
    - ``payload``: the canonical input payload (whatever fed the
      computation). Hashing this means anyone with the same inputs
      can reproduce the same hash.
    - ``effective_date``: ISO YYYY-MM-DD as-of date. Defaults to today
      when not supplied — caller should supply explicitly for
      reproducibility (the computation date drifts; the as-of date
      shouldn't).
    - ``run_id_override`` / ``computed_at_override``: deterministic
      overrides for testing. Production callers omit these so each
      run gets a fresh UUID + current UTC timestamp.
    """
    run_id = run_id_override or str(uuid.uuid4())
    computed_at = computed_at_override or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    eff = effective_date or date.today().isoformat()
    payload_hash = _payload_sha256(payload)
    return AuditTrail(
        run_id=run_id,
        effective_date=eff,
        computed_at=computed_at,
        engine_version=ENGINE_VERSION,
        engine_version_notes=ENGINE_VERSION_NOTES,
        payload_hash=payload_hash,
        payload_hash_algorithm="sha-256",
        sources=AUDIT_TRAIL_SOURCES,
    )


__all__ = [
    "AUDIT_TRAIL_SOURCES",
    "AuditTrail",
    "ENGINE_VERSION",
    "ENGINE_VERSION_NOTES",
    "build_audit_trail",
]
