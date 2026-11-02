"""BET-319 Belgian historical value report contract under Art. 102, § 4 WIB 92.

The Phase-0 spike asks: does ``fiscal_section.build_fiscal_reference_context``
already emit the contents a Belgian capital-gains (meerwaardebelasting)
reference valuation legally needs? This module turns that one-off "confirm"
into an *enforced* contract:

* ``MEERWAARDEBELASTING_CONTRACT_FIELDS`` — the legally-material fields the
  ``FiscalReferenceContext`` shape MUST keep declaring (a companion test pins
  this against the live TypedDict, so the engine can never silently drop one).
* ``validate_fiscal_reference_coverage`` checks whether a report has the
  calculation evidence needed for professional review. It does not replace
  the required independent professional judgement.

Pure (no engine machinery, no DB) → unit-tested directly. The ITAA/IBR
field-list sign-off is the remaining human task of the spike; this locks
whatever is confirmed and catches regressions in the meantime.
"""

from __future__ import annotations

from collections.abc import Mapping

#: Legally-material fields the ``FiscalReferenceContext`` shape must declare for
#: the Art. 102, § 4 WIB 92 reference annex. Pinned by the companion contract test.
MEERWAARDEBELASTING_CONTRACT_FIELDS: tuple[str, ...] = (
    "show_fiscal_reference",
    "fiscal_reference_value",
    "fiscal_reference_year",
    "fiscal_reference_date",
    "fiscal_normalized_ebitda",
    "fiscal_ebitda_multiple",
    "fiscal_ebitda_component",
    "fiscal_book_equity",
    "fiscal_value_complete",
    "fiscal_legal_anchors_acknowledged",
    "fiscal_confirmed_anchors",
    "fiscal_internal_transfer",
    "fiscal_company_role",
    "fiscal_acquisition_cost",
    "fiscal_proven_historical_cost",
    "fiscal_max_anchor_value",
    "fiscal_ebitda_basis",
    "fiscal_show_statutory_ebitda_caution",
    "fiscal_max_anchor_label",
    "fiscal_anchor_1_value",
    "fiscal_anchor_2_value",
    "fiscal_anchor_3_value",
    "fiscal_anchor_4_value",
)

#: Values required for every supported method before professional review.
MEERWAARDEBELASTING_REQUIRED_VALUES: tuple[str, ...] = (
    "fiscal_reference_date",
    "fiscal_max_anchor_value",
    "fiscal_acquisition_cost",
    "fiscal_max_anchor_label",
    "fiscal_legal_anchors_acknowledged",
)

_FORMULA_REQUIRED_VALUES: tuple[str, ...] = (
    "fiscal_reference_value",
    "fiscal_normalized_ebitda",
    "fiscal_ebitda_multiple",
    "fiscal_book_equity",
    "fiscal_ebitda_basis",
    "fiscal_show_statutory_ebitda_caution",
)

_METHOD_VALUE_FIELDS = {
    "anchor_1": "fiscal_anchor_1_value",
    "anchor_2": "fiscal_anchor_2_value",
    "anchor_3": "fiscal_anchor_3_value",
    "anchor_4": "fiscal_anchor_4_value",
}


def validate_fiscal_reference_coverage(context: Mapping[str, object]) -> dict[str, object]:
    """Check whether this annex is ready for professional review.

    The selected method determines the required calculation fields. The
    professional report route does not require a complete statutory formula.
    """
    missing = [f for f in MEERWAARDEBELASTING_REQUIRED_VALUES if f not in context]
    empty = [f for f in MEERWAARDEBELASTING_REQUIRED_VALUES if f in context and context[f] is None]
    invalid: list[str] = []
    if context.get("fiscal_reference_date") not in {"31/12/2025", "2025-12-31"}:
        invalid.append("fiscal_reference_date")
    selected_method = context.get("fiscal_max_anchor_label")
    selected_value_field = _METHOD_VALUE_FIELDS.get(str(selected_method))
    if selected_value_field is None:
        invalid.append("fiscal_max_anchor_label")
    elif selected_value_field not in context:
        missing.append(selected_value_field)
    elif context[selected_value_field] is None:
        empty.append(selected_value_field)

    if selected_method == "anchor_1":
        for field in _FORMULA_REQUIRED_VALUES:
            if field not in context:
                missing.append(field)
            elif context[field] is None:
                empty.append(field)
        if context.get("fiscal_ebitda_basis") != "statutair":
            invalid.append("fiscal_ebitda_basis")
        if context.get("fiscal_show_statutory_ebitda_caution") is not False:
            invalid.append("fiscal_show_statutory_ebitda_caution")
    return {
        "ok": not missing and not empty and not invalid,
        "missing": missing,
        "empty": empty,
        "invalid": invalid,
    }
