"""One DCF cash-tax assumption for forecasts, WACC inputs and disclosures.

Country references are modelling assumptions, not entity-specific tax advice.
Component and distribution taxes cannot be substituted for annual EBIT tax.
Explicit ``_pct`` inputs use percentage points, including rates below 1%.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from src.config.country_packs import country_pack, resolve_country_pack_tax_rate
from src.utils.adaptive_input_helpers import get_business_context
from src.utils.percentage_input_contract import declared_percentage

TAX_POLICY_VERSION = "dcf_tax_policy.v2"


@dataclass(frozen=True)
class DcfTaxAssumption:
    rate: Decimal
    source: str
    country_code: str
    country_pack_version: str
    reasons: tuple[str, ...]
    source_references: tuple[str, ...]

    def provenance(self) -> dict[str, object]:
        return {
            "schema_version": TAX_POLICY_VERSION,
            "rate": float(self.rate * 100),
            "rate_decimal": str(self.rate),
            "rate_unit": "percentage_points",
            "source": self.source,
            # The compatibility source alias does not prove who selected the
            # field: consumers can populate defaults before sending a request.
            "input_origin": (
                "request_field" if self.source == "advisor_override" else "country_policy_reference"
            ),
            "input_origin_verified": False,
            "country_code": self.country_code,
            "country_pack_version": self.country_pack_version,
            "reasons": self.reasons,
            "source_references": self.source_references,
        }


def resolve_dcf_tax_assumption(request: object) -> DcfTaxAssumption:
    code = str(getattr(request, "country_code", "") or "").strip().upper()
    code = "GB" if code == "UK" else code
    pack = country_pack(code)
    if pack is None:
        raise ValueError(f"No DCF country tax policy configured for {code!r}")
    context = get_business_context(request)
    raw = context.get("dcf_tax_rate_pct")
    if raw is not None:
        if isinstance(raw, bool):
            raise ValueError("dcf_tax_rate_pct must be finite percentage points, not a boolean")
        try:
            declared = declared_percentage(context, "dcf_tax_rate_pct")
            pct = declared * 100 if declared is not None else Decimal(str(raw))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("dcf_tax_rate_pct must be finite percentage points") from exc
        if not pct.is_finite() or not Decimal(0) <= pct <= Decimal(100):
            raise ValueError("dcf_tax_rate_pct must be between 0 and 100 percentage points")
        return DcfTaxAssumption(
            rate=pct / 100,
            source="advisor_override",
            country_code=code,
            country_pack_version=pack.pack_version,
            reasons=(
                f"Explicit modeling input: {pct}% applied via dcf_tax_rate_pct; "
                "a constant cash-tax assumption, not verified statutory eligibility.",
                *pack.jurisdiction_restrictions,
            ),
            source_references=pack.official_sources,
        )
    if context.get("sme_rate_override") is True:
        raise ValueError(
            "SME eligibility alone cannot determine a constant DCF cash-tax rate; "
            "supply an explicit dcf_tax_rate_pct assumption or an explicit cash-tax forecast"
        )
    rate = resolve_country_pack_tax_rate(code, context)
    regime_key = (
        str(context.get("irish_tax_regime", "")).strip().lower() if code == "IE" else "standard"
    )
    regime = pack.tax_regimes[regime_key]
    return DcfTaxAssumption(
        rate=rate,
        source="country_pack_reference",
        country_code=code,
        country_pack_version=pack.pack_version,
        reasons=(
            f"{code}: {regime.applicability}. Applied as a constant reference assumption; "
            "entity-specific cash tax, reduced-rate eligibility, tranches and losses are not established.",
            *pack.jurisdiction_restrictions,
        ),
        source_references=(regime.source_url,),
    )
