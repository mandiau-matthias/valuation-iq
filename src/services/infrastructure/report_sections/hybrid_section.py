"""
Hybrid Methodology Section Builder

Extracts DCF/multiples weights from a valuation response using the canonical
contract (no hidden defaults) and returns template context for the hybrid
methodology breakdown on the report.
"""

from decimal import Decimal
from typing import Optional, Protocol, TypeAlias, cast

from src.domain.valuation_contract import extract_methodology_weights
from src.services.infrastructure.translations import (
    ReportTranslations,
    get_translations,
    normalize_report_locale,
)
from src.utils.decimal_helpers import safe_decimal_or_zero as _safe_decimal
from src.utils.decimal_helpers import safe_float as _to_float

JsonMap: TypeAlias = dict[str, object]


class HybridResponseShape(Protocol):
    dcf_valuation: object
    multiples_valuation: object


def _getattr_safe(obj: object, name: str, default: object = None) -> object:
    val = getattr(obj, name, default)
    return default if val is None else val


def _coalesce(*values: object) -> object:
    """Return the first value that is not ``None`` (``0`` is valid)."""
    for v in values:
        if v is not None:
            return v
    return None


def build_hybrid_context(
    response: object,
    locale: str = "nl",
    t: Optional[ReportTranslations] = None,
    country_code: str = "BE",
) -> JsonMap:
    """Build template context for the hybrid methodology breakdown.

    Delegates weight resolution to ``valuation_contract.extract_methodology_weights``
    so there is no hidden 70/30 fallback.  When weights cannot be determined the
    caller receives ``{"is_hybrid": False}`` and must not render a hybrid section.
    """
    canonical = extract_methodology_weights(response)
    if not canonical["is_hybrid"]:
        return {"is_hybrid": False}

    _cc = str(country_code or "BE").strip().upper() or "BE"
    _t = t or get_translations(
        normalize_report_locale(locale),
        country_code=_cc,
    )

    dcf_weight = _safe_decimal(canonical["dcf_weight"])
    multiples_weight = _safe_decimal(canonical["multiples_weight"])

    response_shape = cast(HybridResponseShape, response)
    mv = response_shape.multiples_valuation
    multiples_ev = _coalesce(
        _getattr_safe(mv, "enterprise_value_mid"),
        _getattr_safe(mv, "ev_mid"),
        _getattr_safe(mv, "enterprise_value"),
        _getattr_safe(mv, "equity_value_mid"),
        _getattr_safe(response, "equity_value_mid"),
    )
    multiples_value = _safe_decimal(multiples_ev)

    dcf_ev = _getattr_safe(response_shape.dcf_valuation, "enterprise_value")
    dcf_value = _safe_decimal(dcf_ev)

    weighted_valuation = (multiples_value * multiples_weight) + (dcf_value * dcf_weight)

    return {
        "is_hybrid": True,
        "multiples_weight": _to_float(multiples_weight),
        "dcf_weight": _to_float(dcf_weight),
        "multiples_value": _to_float(multiples_value),
        "dcf_value": _to_float(dcf_value),
        "weighted_valuation": _to_float(weighted_valuation),
        "methodology_breakdown": [
            {
                "method": _t.exec_methodology_badge_multiples,
                "weight": _to_float(multiples_weight),
                "value": _to_float(multiples_value),
                "contribution": _to_float(multiples_value * multiples_weight),
            },
            {
                "method": _t.exec_methodology_badge_dcf,
                "weight": _to_float(dcf_weight),
                "value": _to_float(dcf_value),
                "contribution": _to_float(dcf_value * dcf_weight),
            },
        ],
    }
