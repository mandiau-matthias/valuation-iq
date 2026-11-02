"""
Multiples Converter

Converts multiples_valuation Pydantic models to dictionary structures.
"""

from collections.abc import Iterable, Mapping
from typing import Optional, cast

from src.services.interfaces.request_response_protocol import ValuationResponseProtocol
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _call_mapping_dumper(value: object, method_name: str) -> Optional[dict[str, object]]:
    dumper = getattr(value, method_name, None)
    if not callable(dumper):
        return None
    dumped = dumper()
    return dict(dumped) if isinstance(dumped, dict) else None


def _public_attribute_dict(value: object) -> dict[str, object]:
    result: dict[str, object] = {}
    for attr in dir(value):
        if attr.startswith("_"):
            continue
        try:
            attr_value = getattr(value, attr)
        except (AttributeError, TypeError):
            continue
        if not callable(attr_value):
            result[attr] = attr_value
    return result


def _to_mutable_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)

    for method_name in ("model_dump", "dict"):
        dumped = _call_mapping_dumper(value, method_name)
        if dumped is not None:
            return dumped

    try:
        if isinstance(value, Mapping):
            return dict(cast(Mapping[str, object], value))
        if isinstance(value, Iterable):
            return dict(cast(Iterable[tuple[str, object]], value))
    except (TypeError, ValueError):
        pass
    return _public_attribute_dict(value)


def _get_value(value: object, key: str, default: object = None) -> object:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _apply_final_multiples(
    multiples_dict: dict[str, object],
    *,
    multiples_valuation: object,
    multiple_pipeline: object,
) -> None:
    multiples_dict["final_ebitda_multiple"] = None
    multiples_dict["final_revenue_multiple"] = None

    if multiple_pipeline:
        metric_type = _get_value(multiple_pipeline, "metric_type")
        final_multiple = _get_value(multiple_pipeline, "final_multiple")
        if metric_type == "EBITDA":
            multiples_dict["final_ebitda_multiple"] = final_multiple
        elif metric_type == "Revenue":
            multiples_dict["final_revenue_multiple"] = final_multiple

    ebitda_multiple = multiples_dict.get("ebitda_multiple") or _get_value(
        multiples_valuation, "ebitda_multiple"
    )
    revenue_multiple = multiples_dict.get("revenue_multiple") or _get_value(
        multiples_valuation, "revenue_multiple"
    )
    if multiples_dict["final_ebitda_multiple"] is None and ebitda_multiple:
        multiples_dict["final_ebitda_multiple"] = ebitda_multiple
    if multiples_dict["final_revenue_multiple"] is None and revenue_multiple:
        multiples_dict["final_revenue_multiple"] = revenue_multiple


def _flatten_owner_concentration(multiples_dict: dict[str, object]) -> None:
    multiples_dict["owner_concentration_adjustment_percentage"] = None
    owner_concentration = multiples_dict.get("owner_concentration")
    if not isinstance(owner_concentration, dict):
        return

    if "adjustment_percentage" in owner_concentration:
        multiples_dict["owner_concentration_adjustment_percentage"] = owner_concentration[
            "adjustment_percentage"
        ]
    elif "adjustment_factor" in owner_concentration:
        multiples_dict["owner_concentration_adjustment_percentage"] = (
            owner_concentration["adjustment_factor"] * 100
        )


class MultiplesConverter:
    """
    Converts multiples_valuation to dict and adds final multiples.

    Handles conversion of Pydantic models to dictionaries with proper field mapping.
    """

    @staticmethod
    def convert_to_dict(response: ValuationResponseProtocol) -> Optional[dict[str, object]]:
        """
        Convert multiples_valuation to dict and add final multiples.

        Args:
            response: ValuationResponse containing multiples_valuation

        Returns:
            Dictionary representation of multiples_valuation, or None if not present
        """
        multiples_valuation = response.multiples_valuation
        if not multiples_valuation:
            return None

        multiples_dict = _to_mutable_dict(multiples_valuation)
        _apply_final_multiples(
            multiples_dict,
            multiples_valuation=multiples_valuation,
            multiple_pipeline=getattr(response, "multiple_pipeline", None),
        )
        _flatten_owner_concentration(multiples_dict)
        return multiples_dict
