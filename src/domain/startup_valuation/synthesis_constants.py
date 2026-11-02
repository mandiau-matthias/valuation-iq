"""Immutable policy tables for startup valuation synthesis."""

from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from .schemas import StartupStage

STAGE_WEIGHTS: Mapping[StartupStage, Mapping[str, Decimal]] = MappingProxyType(
    {
        "pre_seed": MappingProxyType(
            {
                "berkus": Decimal("0.45"),
                "scorecard": Decimal("0.30"),
                "vc": Decimal("0.15"),
                "saas_forward": Decimal("0.10"),
            }
        ),
        "seed": MappingProxyType(
            {
                "berkus": Decimal("0.20"),
                "scorecard": Decimal("0.30"),
                "vc": Decimal("0.25"),
                "saas_forward": Decimal("0.25"),
            }
        ),
        "series_a": MappingProxyType(
            {
                "berkus": Decimal("0.10"),
                "scorecard": Decimal("0.20"),
                "vc": Decimal("0.35"),
                "saas_forward": Decimal("0.35"),
            }
        ),
    }
)

FOUNDER_STAGE_WEIGHTS: Mapping[StartupStage, Mapping[str, Decimal]] = MappingProxyType(
    {
        "pre_seed": MappingProxyType(
            {
                "berkus": Decimal("0.55"),
                "vc": Decimal("0.25"),
                "saas_forward": Decimal("0.20"),
            }
        ),
        "seed": MappingProxyType(
            {
                "berkus": Decimal("0.25"),
                "vc": Decimal("0.40"),
                "saas_forward": Decimal("0.35"),
            }
        ),
        "series_a": MappingProxyType(
            {
                "berkus": Decimal("0.10"),
                "vc": Decimal("0.45"),
                "saas_forward": Decimal("0.45"),
            }
        ),
    }
)

LEG_DISPLAY_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "berkus": "Berkus",
        "scorecard": "Scorecard",
        "vc": "VC Method",
        "saas_forward": "SaaS Forward Multiple",
    }
)

CANONICAL_BASIS_KEY_BLENDED: str = "canonical_basis_blended"
CANONICAL_BASIS_KEY_ADVISOR_ONLY: str = "canonical_basis_advisor_only"
CANONICAL_BASIS_KEY_FOUNDER_ONLY: str = "canonical_basis_founder_only"
CANONICAL_BASIS_KEY_INSUFFICIENT: str = "canonical_basis_insufficient"

CANONICAL_BASIS_EN: Mapping[str, str] = MappingProxyType(
    {
        CANONICAL_BASIS_KEY_BLENDED: (
            "Blended median of the advisor 4-leg and founder 3-leg blends "
            "(both reported in the method breakdown)."
        ),
        CANONICAL_BASIS_KEY_ADVISOR_ONLY: (
            "Only the advisor 4-leg blend is available "
            "(the founder 3-leg blend produced no value)."
        ),
        CANONICAL_BASIS_KEY_FOUNDER_ONLY: (
            "Only the founder 3-leg blend is available "
            "(the advisor 4-leg blend produced no value)."
        ),
        CANONICAL_BASIS_KEY_INSUFFICIENT: (
            "Insufficient inputs to produce a defensible pre-money valuation."
        ),
    }
)

__all__ = [
    "CANONICAL_BASIS_EN",
    "CANONICAL_BASIS_KEY_ADVISOR_ONLY",
    "CANONICAL_BASIS_KEY_BLENDED",
    "CANONICAL_BASIS_KEY_FOUNDER_ONLY",
    "CANONICAL_BASIS_KEY_INSUFFICIENT",
    "FOUNDER_STAGE_WEIGHTS",
    "LEG_DISPLAY_NAMES",
    "STAGE_WEIGHTS",
]
