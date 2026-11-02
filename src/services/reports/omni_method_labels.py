"""
Omni method display vs canonical Jinja labels (ADR-001).

Templates branch on English canonical strings (e.g. 'DCF Analysis'). Headlines shown
to Dutch users use localized display strings without breaking those conditionals.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.valuation_contract import method_key_matches

# Dutch accountant-facing headline for DCF; canonical Jinja key stays "DCF Analysis".
NL_DCF_DISPLAY_HEADLINE = "DCF-analyse"


@dataclass(frozen=True)
class OmniMethodLabels:
    """Immutable labels for a selected valuation method."""

    canonical_methodology: str
    display_label: str


def resolve_omni_method_labels(
    *,
    selected_method: str,
    locale: str,
    method_label: str,
) -> OmniMethodLabels:
    """
    Map API method key + locale to canonical (Jinja) vs display (UI) labels.

    - DCF: canonical is always "DCF Analysis"; NL locale uses NL_DCF_DISPLAY_HEADLINE.
    - Other methods: both fields follow the persisted/API method label.
    """
    loc = (locale or "nl").lower()
    is_nl = loc.startswith("nl")

    if method_key_matches(selected_method, "dcf"):
        canonical = "DCF Analysis"
        display = NL_DCF_DISPLAY_HEADLINE if is_nl else method_label
        return OmniMethodLabels(
            canonical_methodology=canonical,
            display_label=display,
        )

    return OmniMethodLabels(
        canonical_methodology=method_label,
        display_label=method_label,
    )
