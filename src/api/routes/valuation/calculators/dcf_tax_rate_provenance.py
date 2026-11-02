"""Report the same tax assumption used by the DCF calculation."""

from src.api.routes.valuation.calculators.dcf_tax_policy import (
    TAX_POLICY_VERSION,
    resolve_dcf_tax_assumption,
)


def build_tax_rate_provenance(request: object) -> dict[str, object]:
    """An unresolved assumption is disclosed without substituting a number."""
    try:
        return resolve_dcf_tax_assumption(request).provenance()
    except ValueError as exc:
        return {
            "schema_version": TAX_POLICY_VERSION,
            "rate": None,
            "rate_decimal": None,
            "source": "unresolved",
            "reasons": (str(exc),),
        }
