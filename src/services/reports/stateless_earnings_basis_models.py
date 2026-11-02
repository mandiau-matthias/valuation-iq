"""Exact annual observations and weights published with the EBITDA basis."""

from dataclasses import dataclass
from decimal import Decimal

from src.api.schemas.stateless_api import TriageFlag
from src.utils.decimal_helpers import safe_decimal_or_zero


@dataclass(frozen=True)
class StatelessEarningsBasis:
    """The exact annual observations and weights that produced the EBITDA basis."""

    normalized_ebitda: Decimal
    reported_ebitda: Decimal
    current_normalized_ebitda: Decimal
    current_reported_ebitda: Decimal
    mode: str
    rows: list[dict[str, object]]
    triage_flags: list[TriageFlag]

    def to_payload(self) -> dict[str, object]:
        return {
            "version": "stateless_earnings_basis_v1",
            "basis": "EBITDA",
            "mode": self.mode,
            "reported_ebitda": self.reported_ebitda,
            "normalized_ebitda": self.normalized_ebitda,
            "current_reported_ebitda": self.current_reported_ebitda,
            "current_normalized_ebitda": self.current_normalized_ebitda,
            "total_adjustments": self.normalized_ebitda - self.reported_ebitda,
            "rows": self.rows,
            "weights_sum": sum(
                (safe_decimal_or_zero(row.get("weight")) for row in self.rows),
                Decimal("0"),
            ),
        }
