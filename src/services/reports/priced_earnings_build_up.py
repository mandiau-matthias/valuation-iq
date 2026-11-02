"""Build the typed earnings summary from the shared, provenance-preserving projection."""

from collections.abc import Mapping

from src.api.schemas.multiple_build_up import EarningsBasisBuildUp
from src.services.reports.earnings_basis_projection import project_earnings_basis_ledger
from src.services.reports.multiple_build_up_assembler import _earnings_basis_build_up
from src.utils.decimal_helpers import optional_decimal


def build_priced_earnings_basis(ledger: Mapping[str, object]) -> EarningsBasisBuildUp:
    """Keep the canonical totals and annual evidence without a second projection algorithm."""
    totals = [
        optional_decimal(ledger.get(key))
        for key in ("reported_ebitda", "normalized_ebitda", "total_adjustments")
    ]
    reported, adjusted, total = totals
    if reported is None or adjusted is None or total is None:
        raise ValueError("canonical earnings ledger requires finite monetary values")
    projection = project_earnings_basis_ledger(ledger)
    basis = _earnings_basis_build_up(
        basis="EBITDA",
        rationale=str(projection["rationale"]),
        reported_earnings=reported,
        adjusted_earnings=adjusted,
        add_back_ledger=projection,
    )
    return basis.model_copy(update={"total_adjustments": total})
