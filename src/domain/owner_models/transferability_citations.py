"""Citations and taxonomy labels for transferability v2."""

from typing import List

from pydantic import BaseModel, ConfigDict


class MethodologyCitation(BaseModel):
    """One line of academic backing for a layer of the v2 model."""

    layer: str
    citation: str
    application: str

    model_config = ConfigDict(use_enum_values=True)


METHODOLOGY_CITATIONS: List[MethodologyCitation] = [
    MethodologyCitation(
        layer="decomposition",
        citation="Damodaran, A. (2012). Investment Valuation, 3rd ed., ch. 24.",
        application=(
            "Key-person discount as a decomposition of operational, relational "
            "and brand dependence - not a single coefficient."
        ),
    ),
    MethodologyCitation(
        layer="decomposition",
        citation="Pratt, S., Reilly, R., Schweihs, R. (2008). Valuing a Business, 5th ed., ch. 28.",
        application=(
            "Transferability framework underlying the 5-cluster grouping: "
            "planning / relationships / operations / knowledge / brand."
        ),
    ),
    MethodologyCitation(
        layer="buyer_profile",
        citation="Pepperdine Private Capital Markets Project (PCMI), 2024 Q4.",
        application=(
            "Buyer-type distribution by deal size, used to set the < €500k / "
            "€500k-€2M / €2M-€10M / >= €10M inflection points."
        ),
    ),
    MethodologyCitation(
        layer="buyer_profile",
        citation="EU Recommendation 2003/361/EC (SME definition).",
        application=(
            "Maps the equity bands to the formal Micro / Small / Medium / "
            "Lower-mid-market segments referenced in the buyer rationale."
        ),
    ),
    MethodologyCitation(
        layer="incidence",
        citation="SBVS (Small Business Valuation Standards), AICPA / NACVA.",
        application=(
            "SDE is already net of owner replacement; only the residual "
            "transition risk on the multiple survives -> 0.7x incidence."
        ),
    ),
    MethodologyCitation(
        layer="incidence",
        citation="Mercer, Z.C. (2001). Quantifying Marketability Discounts.",
        application=(
            "Buyer-pool argument extended to revenue-multiple incidence "
            "(0.6x) - multiples reflect customer-base quality more than "
            "owner-skill dependence."
        ),
    ),
    MethodologyCitation(
        layer="severity",
        citation="Pratt, Reilly & Schweihs (2008), §28.7 - key-person discount range.",
        application=(
            "Severity tiers calibrated to the published -5% to -40% range; "
            "raw discounts are monotonic and conservative within the band."
        ),
    ),
]


EU_SME_SEGMENT_LABELS: dict[str, str] = {
    "individual_operator": "Micro (EU 2003/361: <10 employees, <=€2M turnover)",
    "search_fund": "Small (EU 2003/361: <50 employees, <=€10M turnover)",
    "pe_add_on": "Small / Medium (EU 2003/361: <250 employees, <=€50M turnover)",
    "strategic": "Lower mid-market (above EU SME ceiling)",
    "family_office": "Cross-band (segment depends on platform fit)",
}
