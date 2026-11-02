"""Canonical report-assurance derivation and presentation helpers.

Evidence maturity, evidence confidence, calculation certification, legal
attestation, and realized outcome accuracy are deliberately orthogonal.  This
module is the compatibility boundary while legacy ``data_tier`` fields remain
on the public calculation response.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from src.api.schemas.valuation_assurance_security import ValuationAssuranceEnvelopeV2
from src.api.schemas.valuation_contracts import ReportAssuranceContract
from src.services.reports.valuation_assurance_status import CurrentValuationAssuranceAuthority

CERTIFIED_CALCULATION_STATUSES = frozenset({"certified", "certified_with_qualifications"})


def assurance_from_legacy_response_snapshot(
    snapshot: object,
    *,
    confidence_model_version: str = "evidence_confidence.v1",
) -> ReportAssuranceContract:
    """Map legacy evidence signals without turning them into certification.

    The old ``attested`` label mixed a legal state into the evidence ladder. It
    therefore maps no higher than T3 and does not set legal attestation or
    calculation certification.
    """

    values = dict(snapshot) if isinstance(snapshot, Mapping) else {}
    legacy_tier = str(values.get("data_tier") or "indicative").strip().lower()
    evidence_tier = {
        "indicative": "T2",
        "defensible": "T3",
        "attested": "T3",
    }.get(legacy_tier, "T2")
    declared_level = str(values.get("confidence_level") or "LOW").strip().upper()
    level = declared_level if declared_level in {"LOW", "MEDIUM", "HIGH"} else "LOW"
    try:
        score = int(values.get("confidence_score") or 0)
    except (TypeError, ValueError):
        score = 0
    score = min(max(score, 0), 100)
    rationale = str(values.get("data_tier_rationale") or "").strip() or None
    legacy_value = legacy_tier if legacy_tier in {"indicative", "defensible", "attested"} else None
    return ReportAssuranceContract.model_validate(
        {
            "evidence_maturity": {
                "tier": evidence_tier,
                "rationale": rationale,
                "legacy_data_tier": legacy_value,
            },
            "evidence_confidence": {
                "level": level,
                "score": score,
                "model_version": confidence_model_version,
            },
            "calculation_certification": {"status": "uncertified"},
            "legal_attestation": {
                "status": "not_attested",
                "calculation_certification_effect": "none",
            },
            "outcome_accuracy": {"status": "not_observed"},
        }
    )


def report_assurance_projection(
    run: object,
    *,
    locale: str = "nl",
    report_scope: str = "standard",
    assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> dict[str, object]:
    """Return authenticated assurance facts plus localized presentation labels."""

    schema_version = getattr(run, "schema_version", None)
    assurance = getattr(run, "assurance", None)
    is_canonical = schema_version == "valuation_run.v2" and assurance is not None
    assurance_envelope: ValuationAssuranceEnvelopeV2 | None = (
        assurance_authority.envelope if assurance_authority is not None else None
    )
    has_titan_authority = is_canonical and assurance_envelope is not None
    calculation_status = (
        assurance_envelope.calculation_certification.status
        if has_titan_authority
        else "uncertified"
    )
    country_pack_state = assurance.country_pack_certification_state if is_canonical else "draft"
    certified = (
        has_titan_authority
        and calculation_status in CERTIFIED_CALCULATION_STATUSES
        and country_pack_state == "certified"
        and assurance.method_country_certification_eligible
    )
    certification_status = (
        "canonical_certified"
        if certified
        else "canonical_uncertified" if is_canonical else "legacy_uncertified"
    )
    if report_scope == "client_indicative":
        certification_status = "client_indicative"
    lang = str(locale or "nl").lower()[:2]
    labels = {
        "canonical_certified": {
            "nl": "CANONIEKE BEREKENING · GECERTIFICEERD",
            "en": "CANONICAL CALCULATION · CERTIFIED",
            "fr": "CALCUL CANONIQUE · CERTIFIE",
        },
        "canonical_uncertified": {
            "nl": "CANONIEKE BEREKENING · NIET GECERTIFICEERD",
            "en": "CANONICAL CALCULATION · UNCERTIFIED",
            "fr": "CALCUL CANONIQUE · NON CERTIFIE",
        },
        "legacy_uncertified": {
            "nl": "LEGACYBEREKENING · NIET GECERTIFICEERD",
            "en": "LEGACY CALCULATION · UNCERTIFIED",
            "fr": "CALCUL HERITE · NON CERTIFIE",
        },
        "client_indicative": {
            "nl": "INDICATIEVE WAARDERING · GERAPPORTEERDE EBITDA",
            "en": "INDICATIVE VALUATION · REPORTED EBITDA",
            "fr": "VALORISATION INDICATIVE · EBITDA PUBLIE",
        },
    }
    details = {
        "nl": "Bewijsniveau en vertrouwen zijn geen berekeningscertificaat.",
        "en": "Evidence maturity and confidence are not calculation certification.",
        "fr": "La maturite et la confiance des preuves ne certifient pas le calcul.",
    }
    footer_labels = {
        "canonical_certified": {
            "nl": "CANONIEK - GECERTIFICEERD",
            "en": "CANONICAL - CERTIFIED",
            "fr": "CANONIQUE - CERTIFIE",
        },
        "canonical_uncertified": {
            "nl": "CANONIEK - NIET GECERTIFICEERD",
            "en": "CANONICAL - UNCERTIFIED",
            "fr": "CANONIQUE - NON CERTIFIE",
        },
        "legacy_uncertified": {
            "nl": "LEGACY - NIET GECERTIFICEERD",
            "en": "LEGACY - UNCERTIFIED",
            "fr": "HERITE - NON CERTIFIE",
        },
        "client_indicative": {
            "nl": "INDICATIEF · GERAPPORTEERDE EBITDA",
            "en": "INDICATIVE · REPORTED EBITDA",
            "fr": "INDICATIF · EBITDA PUBLIE",
        },
    }
    attestation_caveats = {
        "nl": (
            "Een handtekening attesteert identiteit en rapportinhoud; "
            "ze certificeert de berekening niet."
        ),
        "en": (
            "A signature attests identity and report content; "
            "it does not certify the calculation."
        ),
        "fr": (
            "Une signature atteste l'identite et le contenu du rapport; "
            "elle ne certifie pas le calcul."
        ),
    }
    country_pack_details = {
        "nl": f"Landpakket {country_pack_state}.",
        "en": f"Country pack {country_pack_state}.",
        "fr": f"Pack pays {country_pack_state}.",
    }
    if has_titan_authority:
        envelope = assurance_envelope
        assert envelope is not None
        exact_score = envelope.evidence_confidence.score
        display_score = int(Decimal(exact_score))
        confidence_level = envelope.evidence_confidence.band.upper()
        payload = {
            "schema_version": "report_assurance.v1",
            "authority": {
                "schema_version": envelope.schema_version,
                "content_hash": envelope.content_hash,
                "component_hash": envelope.component_hash,
                "issuer": envelope.issuer,
                "key_id": envelope.key_id,
                "audience": envelope.audience,
                "observation_ids": list(envelope.observation_ids),
                "observation_set_hash": envelope.observation_set_hash,
                "audience_display_band": envelope.audience_display_band.model_dump(mode="json"),
            },
            "evidence_maturity": {
                "tier": envelope.graph_tier,
                "private_graph_grade": envelope.private_graph_grade,
                "public_value_grade": envelope.public_value_grade,
                "maturity_snapshot_id": envelope.maturity_snapshot_id,
                "maturity_snapshot_fingerprint": envelope.maturity_snapshot_fingerprint,
            },
            "evidence_confidence": {
                "level": confidence_level,
                "score": exact_score,
                "components": envelope.evidence_confidence.components,
                "model_version": envelope.evidence_confidence.model_version,
            },
            "calculation_certification": envelope.calculation_certification.model_dump(mode="json"),
            "legal_attestation": envelope.legal_attestation.model_dump(mode="json"),
            "outcome_accuracy": envelope.outcome_accuracy.model_dump(mode="json"),
            "publication": envelope.publication.model_dump(mode="json"),
            "country_pack_certification_state": country_pack_state,
            "country_pack_certification_manifest_hash": (
                assurance.country_pack_certification_manifest_hash
            ),
            "country_pack_certification_reviewer_receipt_ids": list(
                assurance.country_pack_certification_reviewer_receipt_ids
            ),
            "method_certification_profile_version": (
                assurance.method_certification_profile_version
            ),
            "priced_method_certification_profile_keys": list(
                assurance.priced_method_certification_profile_keys
            ),
            "method_country_certification_eligible": (
                assurance.method_country_certification_eligible
            ),
        }
    else:
        payload = (
            assurance.model_dump(mode="json")
            if is_canonical
            else ReportAssuranceContract().model_dump(mode="json")
        )
        # Preserve any historical declarations inside the hashed run, but do
        # not project them as authenticated report authority.
        payload["calculation_certification"] = {"status": "uncertified"}
        payload["legal_attestation"] = {
            "status": "not_attested",
            "calculation_certification_effect": "none",
        }
        payload["outcome_accuracy"] = {"status": "not_observed"}
        if is_canonical and assurance.evidence_maturity.tier in {"T4", "T5"}:
            payload["evidence_maturity"] = {
                "tier": None,
                "declared_tier": assurance.evidence_maturity.tier,
                "authority_status": "unverified",
                "rationale": (
                    "T4/T5 maturity is Titan-derived and requires a current assurance authority."
                ),
            }
        exact_score = str(assurance.evidence_confidence.score) if is_canonical else None
        display_score = assurance.evidence_confidence.score if is_canonical else None
        confidence_level = assurance.evidence_confidence.level if is_canonical else None
    return {
        "report_assurance": payload,
        "valuation_assurance_envelope": (
            assurance_envelope.model_dump(mode="json") if has_titan_authority else None
        ),
        "assurance_authority_status": "verified" if has_titan_authority else "missing",
        "assurance_audience": assurance_envelope.audience if has_titan_authority else None,
        "assurance_observation_ids": (
            list(assurance_envelope.observation_ids) if has_titan_authority else []
        ),
        "assurance_observation_set_hash": (
            assurance_envelope.observation_set_hash if has_titan_authority else None
        ),
        "assurance_audience_display_band": (
            assurance_envelope.audience_display_band.model_dump(mode="json")
            if has_titan_authority
            else None
        ),
        "assurance_content_hash": (
            assurance_envelope.content_hash if has_titan_authority else None
        ),
        "assurance_component_hash": (
            assurance_envelope.component_hash if has_titan_authority else None
        ),
        "report_certification_status": certification_status,
        "report_certification_label": labels[certification_status].get(
            lang, labels[certification_status]["en"]
        ),
        "report_certification_footer_label": footer_labels[certification_status].get(
            lang, footer_labels[certification_status]["en"]
        ),
        "report_certification_detail": (
            f"{details.get(lang, details['en'])} "
            f"{country_pack_details.get(lang, country_pack_details['en'])}"
        ),
        "legal_attestation_calculation_caveat": attestation_caveats.get(
            lang, attestation_caveats["en"]
        ),
        "evidence_maturity_tier": (
            assurance_envelope.graph_tier
            if has_titan_authority
            else (
                assurance.evidence_maturity.tier
                if is_canonical and assurance.evidence_maturity.tier not in {"T4", "T5"}
                else None
            )
        ),
        "private_graph_grade": (
            assurance_envelope.private_graph_grade if has_titan_authority else None
        ),
        "public_value_grade": (
            assurance_envelope.public_value_grade if has_titan_authority else None
        ),
        "evidence_confidence_level": confidence_level,
        "evidence_confidence_score": display_score,
        "evidence_confidence_score_exact": exact_score,
        "calculation_certification_status": calculation_status,
        "legal_attestation_status": (
            assurance_envelope.legal_attestation.status if has_titan_authority else "not_attested"
        ),
        "outcome_accuracy_status": (
            assurance_envelope.outcome_accuracy.status if has_titan_authority else "not_observed"
        ),
        "country_pack_certification_state": country_pack_state,
        "country_pack_certification_manifest_hash": (
            assurance.country_pack_certification_manifest_hash if is_canonical else None
        ),
        "country_pack_certification_reviewer_receipt_ids": (
            list(assurance.country_pack_certification_reviewer_receipt_ids) if is_canonical else []
        ),
        "method_certification_profile_version": (
            assurance.method_certification_profile_version if is_canonical else None
        ),
        "priced_method_certification_profile_keys": (
            list(assurance.priced_method_certification_profile_keys) if is_canonical else []
        ),
        "method_country_certification_eligible": (
            assurance.method_country_certification_eligible if is_canonical else False
        ),
    }
