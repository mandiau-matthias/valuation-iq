"""Canonical valuation method-key registry.

Introduced 2026-05-15 as Phase 2 of the report-architecture refactor.
Closes a known drift gap between three places that all encode the same
set of method identifiers:

  * Engine MethodResult instances stamp `method_key=<key>` in
    `src/domain/methods/*.py` (Foundation phase, 2026-05-15).
  * The Jinja citation registry in
    `src/templates/main_report/components/_method_citations.html`
    looks up subtitle text + academic sources by key.
  * Hermes' `valuation_method_readiness` contract advertises which
    methods can run for a given input shape — the
    `domain/startup_valuation/synthesis.py:823` comment explicitly
    notes that the keys "mirror Hermes' SME contract".

Before this module landed, each consumer typed the key as a plain
`str`, so a typo (e.g. `"sde"` vs `"sde_multiple"`) became a silent
"empty citations" footer in the rendered report rather than an early
validation failure.  The Foundation phase actually hit this drift —
SDE was initially stamped as `"sde"`, which silently disabled its
citation block until a test caught it.

With `MethodKey` typed as a Literal, a Pydantic validation error
fires the moment an engine constructs `MethodResult(method_key="sde")`,
and the tests in `tests/unit/domain/methods/test_method_keys.py` pin
the Literal against the citation registry so adding a registry entry
without updating the Literal also fails.

CROSS-APP CONSUMERS

Mercury, Venus, and Titan validate their TypeScript registries against
``contracts/valuation-methods.v1.json``. Export/check this owner contract
with ``scripts/export_method_contract.py`` and update consumer snapshots
explicitly. Keep these tuples authoritative; consumer tests pin request
keys, result keys, weights, aliases and ordering.
"""

from typing import Literal


# Source-of-truth tuple for report-facing method identifiers. Order:
# SME track first (visible on the default report), then specialty tracks,
# then registry-only entries (no engine file yet — kept for forward-compat).
METHOD_KEYS: tuple[str, ...] = (
    # Engine-backed, SME track — each is rendered on its own dossier page
    # via `shared/macros/method_section.html`:
    "dcf",
    "ebitda_multiple",
    # Both names are accepted while Venus and the calculation map finish
    # converging. `omzet_multiple` is the user-weight/calc-map key;
    # `revenue_multiple` is the MethodResult/citation key.
    "omzet_multiple",
    "revenue_multiple",
    "sde_multiple",
    "adjusted_nav",
    "holding_sotp",
    "upswitch_adaptive",
    # Engine-backed, forward-compat (no dedicated dossier page yet):
    "arr_multiple",
    "real_estate_yield",
    "fiscal_4x",
    # Engine-backed, specialty tracks (own page sequences, not the
    # method-section macro):
    "liquidation_analysis",
    "startup_valuation",
    # Registry-only (no engine file yet — kept so adding the engine
    # later doesn't require touching this constant):
    "pe_ratio",
    "owner_adaptive",
    "custom_weighted",
    # Citation-routing key for the Adaptive multiples-only presentation.
    "upswitch_adaptive_multiples_only",
)


MethodKey = Literal[
    "dcf",
    "ebitda_multiple",
    "omzet_multiple",
    "revenue_multiple",
    "sde_multiple",
    "adjusted_nav",
    "holding_sotp",
    "upswitch_adaptive",
    "arr_multiple",
    "real_estate_yield",
    "fiscal_4x",
    "liquidation_analysis",
    "startup_valuation",
    "pe_ratio",
    "owner_adaptive",
    "custom_weighted",
    "upswitch_adaptive_multiples_only",
]
"""Typed alias used by `MethodResult.method_key` and any consumer that
takes a method key argument.  Keep in lockstep with `METHOD_KEYS` —
the test in `test_method_keys.py::test_literal_matches_tuple` pins
the two together.
"""


CANONICAL_METHOD_KEYS: tuple[str, ...] = (
    "upswitch_adaptive",
    "ebitda_multiple",
    "omzet_multiple",
    "dcf",
    "sde_multiple",
    "arr_multiple",
    "adjusted_nav",
    "real_estate_yield",
    "fiscal_4x",
    "startup_valuation",
    "liquidation_analysis",
)
"""Calculation/report contract keys for engine outputs and user weights.

`revenue_multiple` remains a public alias for the historical Dutch
`omzet_multiple` key until all frontend/backend consumers converge.
"""


CANONICAL_RUNTIME_METHOD_KEYS: tuple[str, ...] = (
    *CANONICAL_METHOD_KEYS,
    # SOTP is selected by governed group-structure evidence rather than a
    # caller's selected_method/user_weights command, but it is an executable
    # canonical ValuationIQ result and must participate in registry drift
    # checks.
    "holding_sotp",
)
"""Methods that can actually enter a sealed canonical stateless run.

This is deliberately narrower than ``METHOD_KEYS`` (which also contains
legacy/report-forward-compat identifiers) and slightly wider than the public
request keys because holding SOTP is evidence-routed server-side.
"""


DISTINCT_METHOD_COUNT = 11


METHOD_KEY_ALIASES: dict[str, str] = {"revenue_multiple": "omzet_multiple"}
REVENUE_METHOD_KEYS: frozenset[str] = frozenset({"omzet_multiple", "revenue_multiple"})

SELECTED_METHOD_KEY_ALIASES: dict[str, str] = {
    "adaptive": "upswitch_adaptive",
    "ebitda": "ebitda_multiple",
    "revenue": "omzet_multiple",
    "omzet": "omzet_multiple",
    "sde": "sde_multiple",
    "arr": "arr_multiple",
    "nav": "adjusted_nav",
    "property_yield": "real_estate_yield",
    "yield": "real_estate_yield",
    "fiscal": "fiscal_4x",
    "liquidation": "liquidation_analysis",
    "startup": "startup_valuation",
}
"""Short, unambiguous aliases accepted only for ``selected_method``.

User synthesis weights remain canonical-key-only (apart from the historical
``revenue_multiple`` alias). A selected headline is a single-method command,
so these familiar UI shorthands can be normalized without creating duplicate
keys or ambiguous weighted instructions.
"""


PRIMARY_OMNI_METHOD_KEYS: tuple[str, ...] = (
    "upswitch_adaptive",
    "arr_multiple",
    "ebitda_multiple",
    "omzet_multiple",
    "revenue_multiple",
    "sde_multiple",
    "dcf",
    "adjusted_nav",
    "real_estate_yield",
    "fiscal_4x",
    "liquidation_analysis",
)
"""Product/UI order for the default OmniCalc result surface.

This includes the public ``revenue_multiple`` alias so older English-
language result payloads sort next to ``omzet_multiple``. The standalone
startup path is deliberately excluded from the primary Omni list because
it has a separate venture/startup input flow.
"""


OMNI_CALC_PATCHABLE_METHOD_KEYS: tuple[str, ...] = (
    "upswitch_adaptive",
    "ebitda_multiple",
    "dcf",
    "sde_multiple",
    "arr_multiple",
    "omzet_multiple",
    "revenue_multiple",
    "adjusted_nav",
    "real_estate_yield",
    "fiscal_4x",
    "startup_valuation",
    "liquidation_analysis",
)
"""Method keys accepted for report recalculation / selected-method PATCH.

Includes ``startup_valuation`` so an owner-founder report can move into
the standalone venture path, and ``liquidation_analysis`` as the downside
premise-of-value lens.
"""


NON_COMBINABLE_METHOD_KEYS: frozenset[str] = frozenset(
    {
        "startup_valuation",
        "liquidation_analysis",
        "real_estate_yield",
    }
)
"""Standalone tracks that cannot be blended with other user-weighted methods."""


USER_WEIGHT_METHOD_KEYS: frozenset[str] = frozenset(
    set(CANONICAL_METHOD_KEYS) | set(METHOD_KEY_ALIASES)
)
"""Raw keys accepted in `CalculateRequest.user_weights` before normalization."""


def normalize_method_key(method_key: object) -> str:
    """Normalize UI/API method-key spelling to the canonical contract key."""
    if method_key is None:
        return ""
    if isinstance(method_key, str):
        raw = method_key
    else:
        raw = (
            getattr(method_key, "value", None)
            or getattr(method_key, "name", None)
            or str(method_key)
        )
    normalized = "_".join(str(raw).strip().lower().replace("-", "_").split())
    return METHOD_KEY_ALIASES.get(normalized, normalized)


def normalize_selected_method_key(method_key: object) -> str:
    """Normalize a selected-headline method and its supported UI aliases."""
    normalized = normalize_method_key(method_key)
    return SELECTED_METHOD_KEY_ALIASES.get(normalized, normalized)
