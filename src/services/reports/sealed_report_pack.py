"""Closed, audited composition manifest for publishable memoranda.

The legacy report tree remains available to diagnostic previews only. Every
publishable method family uses this small template pack and the immutable
``sealed_memorandum`` display model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


class SealedReportPackError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SealedReportSection:
    section_id: str
    template_name: str

    def as_context(self, **metadata: object) -> dict[str, object]:
        return {
            "id": self.section_id,
            "pdf_template": self.template_name,
            **metadata,
        }


def _sealed(section_id: str) -> SealedReportSection:
    return SealedReportSection(
        section_id=section_id,
        template_name=f"main_report_pdf/sealed/{section_id}.html",
    )


SEALED_MEMORANDUM_PACK = (
    _sealed("cover_page"),
    _sealed("engagement_scope"),
    _sealed("professional_basis"),
    _sealed("company_financial_overview"),
    _sealed("business_market_analysis"),
    _sealed("executive_summary"),
    _sealed("normalization_bridge"),
    _sealed("method_selection"),
    _sealed("method_analysis"),
    _sealed("reconciliation"),
    _sealed("evidence_appendix"),
    _sealed("review_attestation"),
    _sealed("disclaimers"),
)

_METHOD_FAMILY_SECTION_IDS = {
    "upswitch_adaptive",
    "dcf",
    "adjusted_nav",
    "ebitda_multiple",
    "sde",
    "revenue_multiple",
    "holding_sotp",
    "saas_appendix",
    "fiscal_reference",
}


def sealed_template_registry() -> dict[str, str]:
    return {
        section.section_id: section.template_name
        for section in SEALED_MEMORANDUM_PACK
        if section.section_id != "disclaimers"
    }


def _source_sections(context: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw = context.get("sme_report_sections")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return []
    sections = [value for value in raw if isinstance(value, Mapping)]
    if len(sections) != len(raw):
        raise SealedReportPackError("sealed source method manifest is malformed")
    return sections


def _method_metadata(context: Mapping[str, object]) -> dict[str, object]:
    if context.get("is_startup_valuation_report"):
        return {
            "method_family_ids": ["startup_valuation"],
            "method_component_coverages": [],
        }
    if context.get("is_liquidation_report"):
        return {
            "method_family_ids": ["liquidation_analysis"],
            "method_component_coverages": [],
        }
    source = _source_sections(context)
    method_family_ids = [
        str(section.get("id") or "")
        for section in source
        if section.get("method_key")
        or str(section.get("id") or "") in _METHOD_FAMILY_SECTION_IDS
    ]
    coverages = [
        {
            "section_id": str(section.get("id") or ""),
            "coverage": section.get("method_component_coverage"),
        }
        for section in source
        if section.get("method_key")
        or str(section.get("id") or "") in _METHOD_FAMILY_SECTION_IDS
    ]
    if not method_family_ids:
        raise SealedReportPackError("sealed SME report has no method family")
    return {
        "method_family_ids": method_family_ids,
        "method_component_coverages": coverages,
    }


def build_sealed_report_pack(context: Mapping[str, object]) -> list[dict[str, object]]:
    """Return the only section manifest accepted by publishable rendering."""

    method_metadata = _method_metadata(context)
    result: list[dict[str, object]] = []
    memorandum = context.get("sealed_memorandum")
    normalizations: Mapping[str, object] = {}
    if isinstance(memorandum, Mapping):
        candidate = memorandum.get("normalizations")
        if isinstance(candidate, Mapping):
            normalizations = candidate
    compact_normalizations = normalizations.get("compact_on_overview") is True
    professional_basis = False
    business_analysis = False
    if isinstance(memorandum, Mapping):
        scope = memorandum.get("scope")
        if isinstance(scope, Mapping):
            professional = scope.get("professional")
            professional_basis = (
                isinstance(professional, Mapping)
                and professional.get("enabled") is True
            )
            business = scope.get("business")
            business_analysis = (
                isinstance(business, Mapping) and business.get("enabled") is True
            )
    for section in SEALED_MEMORANDUM_PACK:
        if section.section_id == "disclaimers":
            continue
        if section.section_id == "normalization_bridge" and compact_normalizations:
            continue
        if section.section_id == "professional_basis" and not professional_basis:
            continue
        if (
            section.section_id in {"business_market_analysis", "method_selection"}
            and not business_analysis
        ):
            continue
        metadata = method_metadata if section.section_id == "method_analysis" else {}
        result.append(section.as_context(**metadata))
    return result
