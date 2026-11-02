"""Protected Upswitch report design contract and deterministic cover artwork.

The publishable renderer must never fetch fonts, icons or illustrations at
render time.  This module keeps the existing Upswitch visual language explicit
and hashable while turning the cover's former emoji watermark into audited SVG
geometry.  Templates only position the precomputed geometry returned here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from src.services.reports.stateless_valuation_run import canonical_hash


class ReportDesignManifestError(ValueError):
    pass


_FONT_FILES = {
    "satoshi_regular": "Satoshi-Regular.woff2",
    "satoshi_medium": "Satoshi-Medium.woff2",
    "satoshi_bold": "Satoshi-Bold.woff2",
    "satoshi_black": "Satoshi-Black.woff2",
    "jetbrains_mono": "JetBrainsMono.woff2",
}

_EXPECTED_FONT_HASHES = {
    "satoshi_regular": "50dca57f0b77918e0fb7dac998c3f5ef6b0c2a29657da97658a04f98ac532fc5",
    "satoshi_medium": "af02a72246f53ad49c44a591921edbd39ec8258a03d8cc2e0532aa1e497e85b4",
    "satoshi_bold": "353a7fbfb4475f0c31470a7449226006cb64211c71055ca9db860a8acdaa9f68",
    "satoshi_black": "bd11b5820231420e78046c611aebdd628dc17ad67788258ffe3fe902253efd3b",
    "jetbrains_mono": "2c32b9b3ee358c119e210f6f5195f9bd34894d78a785ff2e95d60e718e400af4",
}

_COLOR_TOKENS = {
    "cover": "#121519",
    "ink": "#1A1D22",
    "paper": "#FFFFFF",
    "teal": "#2BA899",
    "teal_light": "#E4F5F2",
    "peach": "#C87F63",
    "muted": "#737985",
    "hairline": "#DFE2E7",
}

_SPACING_SCALE_PT = [4, 6, 8, 10, 12, 16, 24, 32]

# Paths are deliberately simple and monochrome.  They are category anchors,
# not decorative clip art.  The registry is versioned because changing a path
# changes the recognizable cover and therefore the design commitment.
_ICON_PATHS = {
    "trade": "M24 42h72l11 34H35z M38 51h44v18H43z M30 42l12-16h42l12 16z M47 76v22 M73 76v22",
    "real_estate": "M29 98V45l31-22 31 22v53 M43 98V57h34v41 M53 98V76h14v22",
    "technology": "M33 29h54v54H33z M43 40h34v32H43z M47 20v9 M60 20v9 M73 20v9 M47 83v9 M60 83v9 M73 83v9 M24 47h9 M24 60h9 M24 73h9 M87 47h9 M87 60h9 M87 73h9",
    "manufacturing": "M26 98V55l23 13V53l24 15V43l22 13v42z M38 83h12 M59 83h12 M80 83h8 M31 98h63",
    "professional_services": "M31 98V37h58v61 M43 37V25h34v12 M43 55h11 M66 55h11 M43 71h11 M66 71h11 M53 98V84h14v14",
    "hospitality": "M27 95h66 M34 80h52 M40 80c0-22 9-35 20-35s20 13 20 35 M60 38v7 M50 95h20",
    "healthcare": "M44 27h32v20h20v32H76v20H44V79H24V47h20z",
    "transport": "M25 75h70l-8-27H49L38 31H25z M43 75a9 9 0 1 1-18 0 M87 75a9 9 0 1 1-18 0 M49 48v27",
    "construction": "M27 98h66 M37 98V54h46v44 M43 54l17-30 17 30 M48 72h10 M65 72h10",
    "generic": "M30 31h60v67H30z M42 45h36 M42 59h36 M42 73h22 M42 87h14",
}

_CATEGORY_KEYWORDS = {
    "real_estate": ("real estate", "vastgoed", "immobilier", "property"),
    "technology": ("software", "saas", "technology", "technologie", "it "),
    "manufacturing": ("manufact", "productie", "industrie", "fabrication"),
    "professional_services": (
        "account",
        "consult",
        "advis",
        "professional service",
        "zakelijke dienst",
    ),
    "hospitality": ("hotel", "restaurant", "hospitality", "horeca"),
    "healthcare": ("health", "zorg", "medical", "medisch", "santé"),
    "transport": ("transport", "logistic", "mobil", "freight"),
    "construction": ("construction", "bouw", "installat", "entrepreneur"),
    "trade": ("wholesale", "retail", "trade", "handel", "commerce"),
}


def _font_hashes() -> dict[str, str]:
    font_root = Path(__file__).resolve().parents[2] / "assets" / "fonts"
    actual: dict[str, str] = {}
    for font_id, filename in _FONT_FILES.items():
        path = font_root / filename
        if not path.is_file():
            raise ReportDesignManifestError(f"protected font is missing: {filename}")
        actual[font_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != _EXPECTED_FONT_HASHES:
        raise ReportDesignManifestError(
            "protected font bytes changed without a report design manifest revision"
        )
    return actual


def _resolve_icon_id(industry: object, category: object = None) -> str:
    requested = str(category or "").strip().lower().replace("-", "_").replace(" ", "_")
    if requested in _ICON_PATHS:
        return requested
    label = str(industry or "").strip().lower()
    for icon_id, needles in _CATEGORY_KEYWORDS.items():
        if any(needle in label for needle in needles):
            return icon_id
    return "generic"


def _logo_asset(branding: Mapping[str, object]) -> dict[str, object]:
    return {
        "sha256": branding.get("logo_sha256"),
        "intrinsic_width_px": branding.get("logo_width_px"),
        "intrinsic_height_px": branding.get("logo_height_px"),
        "render_width_mm": 58,
        "render_height_mm": 18,
    }


def build_report_design_manifest(
    *, branding: Mapping[str, object], locale: str
) -> dict[str, object]:
    """Return the exact brand-protected design facts committed by a render."""

    manifest = {
        "schema_version": "report_design_manifest.v1",
        "design_profile": "upswitch_advisor_memorandum.v1",
        "locale": locale,
        "fonts": _font_hashes(),
        "colors": dict(_COLOR_TOKENS),
        "spacing_scale_pt": list(_SPACING_SCALE_PT),
        "advisor_logo": _logo_asset(branding),
        "upswitch_logo": {
            "asset_id": "upswitch_wordmark_inline.v1",
            "sha256": canonical_hash(
                {
                    "mark": "rounded-switch-48.v1",
                    "wordmark": "Upswitch",
                    "color": _COLOR_TOKENS["peach"],
                }
            ),
            "render_width_mm": 58,
            "render_height_mm": 18,
        },
        "cover_archetype_revision": "dark_icon_watermark.v4",
        "page_archetype_revision": "sealed_adaptive_pages.v4",
        "industry_icon_registry_revision": "industry_icon_registry.v1",
        "industry_icon_registry_hash": canonical_hash(_ICON_PATHS),
        "business_card_motif_revision": "business_card_knowledge_graph.v1",
        "business_card_motif_hash": canonical_hash(
            {
                "card_path": "M15 18h90v84H15z",
                "edges": ["M78 42L101 26", "M82 61L108 61", "M75 79L101 94"],
                "nodes": [[103, 25, 3], [110, 61, 3], [103, 95, 3]],
                "opacity": "0.05",
            }
        ),
        "chart_specification_hashes": {
            "financial_history": canonical_hash("financial_history_indexed_svg.v2"),
            "normalization_bridge": canonical_hash("normalization_waterfall_svg.v3"),
            "benchmark_distribution": canonical_hash("benchmark_distribution_svg.v2"),
            "ev_to_equity": canonical_hash("ev_to_equity_svg.v3"),
            "method_value_bars": canonical_hash("method_value_bars_svg.v2"),
        },
        "template_contract_version": "ma_valuation_memorandum.v3",
    }
    return manifest


def build_cover_motif(
    *,
    industry: object,
    category: object = None,
    company_name: object = None,
    advisor_logo: Mapping[str, object] | None = None,
    enabled: bool = True,
) -> dict[str, object]:
    icon_id = _resolve_icon_id(industry, category)
    company_label = str(company_name or "").strip()
    industry_label = str(industry or "").strip()
    logo = advisor_logo or {}
    logo_width = logo.get("intrinsic_width_px")
    logo_height = logo.get("intrinsic_height_px")
    logo_geometry_safe = True
    if isinstance(logo_width, int) and isinstance(logo_height, int) and logo_height > 0:
        logo_geometry_safe = Decimal(str(logo_width)) / Decimal(str(logo_height)) <= Decimal("8")
    crowding_safe = len(company_label) <= 42 and len(industry_label) <= 72
    motif_enabled = bool(enabled and logo_geometry_safe and crowding_safe)
    motif = {
        "enabled": motif_enabled,
        "layout_status": (
            "safe"
            if motif_enabled
            else "disabled_logo_geometry" if not logo_geometry_safe else "disabled_crowding"
        ),
        "view_box": "0 0 120 120",
        "icon_id": icon_id,
        "icon_path": _ICON_PATHS[icon_id],
        "card_path": "M15 18h90v84H15z",
        "edges": [
            {"path": "M78 42L101 26"},
            {"path": "M82 61L108 61"},
            {"path": "M75 79L101 94"},
        ],
        "nodes": [
            {"cx": "103", "cy": "25", "radius": "3"},
            {"cx": "110", "cy": "61", "radius": "3"},
            {"cx": "103", "cy": "95", "radius": "3"},
        ],
    }
    motif["motif_sha256"] = canonical_hash(motif)
    return motif
