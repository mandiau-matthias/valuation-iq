"""Company registry context extraction for report aggregation."""

import re
from datetime import date, datetime
from typing import Protocol, TypeGuard

from src.services.reports.protocol_adapter import DictWrapper, _unwrap
from src.services.reports.report_industry_display import detect_business_type_nace_mismatch

# Compact legal-form tokens that indicate a non-profit (VZW/ASBL/AISBL/IVZW).
# We match against the stripped, lowercased, whitespace-collapsed form of
# legal_form so "V.Z.W.", "VZW", "vzw", and "Vereniging zonder winstoogmerk"
# all resolve to True.
_VZW_COMPACT_TOKENS: frozenset[str] = frozenset(
    {"vzw", "ivzw", "asbl", "aisbl", "vog", "aivzw"}
)
_VZW_PHRASE_RE = re.compile(
    r"(zonder\s+winstoogmerk|sans\s+but\s+lucratif|non.?profit|association\s+internationale)",
    re.IGNORECASE,
)


def is_vzw_legal_form(legal_form: object) -> bool:
    """Return True when legal_form indicates a Belgian/European non-profit entity."""
    if not legal_form or not isinstance(legal_form, str):
        return False
    stripped = legal_form.strip()
    compact = re.sub(r"[\s.\-_]", "", stripped).lower()
    if compact in _VZW_COMPACT_TOKENS:
        return True
    return bool(_VZW_PHRASE_RE.search(stripped))

RegistryMap = dict[str, object]


class Gettable(Protocol):
    def get(self, key: str, default: object = None) -> object: ...


class LoggerLike(Protocol):
    def debug(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


def initial_kbo_company_data(registration_number: str | None) -> RegistryMap:
    """Return the default KBO company context."""
    return {
        "has_kbo_data": False,
        "kbo_number": registration_number,
        "legal_form": None,
        "legal_form_full": None,
        "founding_date": None,
        "founded_year": None,
        "company_age_years": None,
        "kbo_nace_code": None,
        "kbo_nace_description": None,
        "kbo_status": None,
        "kbo_address": None,
        "kbo_municipality": None,
        "kbo_postal_code": None,
    }


def _is_gettable(value: object) -> TypeGuard[Gettable]:
    return bool(value) and hasattr(value, "get") and callable(value.get)


def _address_text(raw_address: object) -> str | None:
    address = _unwrap(raw_address) if isinstance(raw_address, DictWrapper) else raw_address
    if isinstance(address, dict):
        rendered = f"{address.get('street', '')} {address.get('house_number', '')}".strip()
        return rendered or None
    if address:
        return str(address)
    return None


def _apply_kbo_enrichment(kbo_data: RegistryMap, enrichment: object) -> None:
    if not _is_gettable(enrichment):
        return

    kbo_data["has_kbo_data"] = True
    kbo_data["legal_form"] = enrichment.get("legal_form")
    kbo_data["legal_form_full"] = enrichment.get("legal_form_full")
    kbo_data["founding_date"] = enrichment.get("founding_date")
    kbo_data["kbo_nace_code"] = enrichment.get("nace_code") or enrichment.get(
        "primary_activity_code"
    )
    kbo_data["kbo_nace_description"] = enrichment.get("nace_description") or enrichment.get(
        "primary_activity_description"
    )
    kbo_data["kbo_status"] = enrichment.get("status")
    kbo_data["kbo_municipality"] = enrichment.get("municipality")
    kbo_data["kbo_postal_code"] = enrichment.get("postal_code")
    if enrichment.get("address"):
        kbo_data["kbo_address"] = _address_text(enrichment.get("address"))


def _apply_loose_registry_fields(kbo_data: RegistryMap, detailed_results: Gettable) -> None:
    if not kbo_data["legal_form"]:
        kbo_data["legal_form"] = detailed_results.get("legal_form")
    if not kbo_data["founding_date"]:
        kbo_data["founding_date"] = detailed_results.get("founding_date")
    if not kbo_data["kbo_nace_code"]:
        kbo_data["kbo_nace_code"] = detailed_results.get("nace_code") or detailed_results.get(
            "activity_code"
        )
    if not kbo_data["kbo_municipality"]:
        kbo_data["kbo_municipality"] = detailed_results.get("municipality") or detailed_results.get(
            "city"
        )
    if not kbo_data["kbo_postal_code"]:
        kbo_data["kbo_postal_code"] = detailed_results.get("postal_code")


def _request_attr(request: object | None, name: str) -> object | None:
    if request is None:
        return None
    if hasattr(request, name):
        return getattr(request, name, None)
    if _is_gettable(request):
        return request.get(name)
    return None


def _apply_request_registry_fields(kbo_data: RegistryMap, request: object | None) -> None:
    """Use request-level registry fields when Titan did not enrich detailed_results."""
    if not request:
        return

    if not kbo_data["legal_form"]:
        kbo_data["legal_form"] = _request_attr(request, "legal_form")
    if not kbo_data["kbo_municipality"]:
        kbo_data["kbo_municipality"] = _request_attr(request, "city")
    if not kbo_data["kbo_postal_code"]:
        kbo_data["kbo_postal_code"] = _request_attr(request, "postal_code")


def _apply_founding_age(kbo_data: RegistryMap) -> None:
    founding = kbo_data.get("founding_date")
    if not founding:
        return

    if isinstance(founding, str):
        try:
            if len(founding) >= 4:
                kbo_data["founded_year"] = int(founding[:4])
        except (ValueError, TypeError):
            return
    elif isinstance(founding, (date, datetime)):
        kbo_data["founded_year"] = founding.year

    if kbo_data["founded_year"]:
        kbo_data["company_age_years"] = datetime.now().year - kbo_data["founded_year"]


def _mark_success(
    kbo_data: RegistryMap,
    registration_number: str | None,
    logger: LoggerLike | None,
) -> None:
    if not (
        kbo_data["legal_form"]
        or kbo_data["founding_date"]
        or kbo_data["kbo_nace_code"]
        or kbo_data["kbo_municipality"]
        or kbo_data["kbo_postal_code"]
        or kbo_data["kbo_address"]
    ):
        return
    kbo_data["has_kbo_data"] = True
    if logger:
        logger.info(
            f"\u2705 KBO data extracted for {registration_number}",
            extra={
                "legal_form": kbo_data["legal_form"],
                "founded_year": kbo_data["founded_year"],
                "nace_code": kbo_data["kbo_nace_code"],
            },
        )


def build_kbo_company_data(
    *,
    registration_number: str | None,
    response: object,
    request: object | None = None,
    logger: LoggerLike | None = None,
) -> RegistryMap:
    """Build company registry context from Titan-enriched response data."""
    kbo_data = initial_kbo_company_data(registration_number)
    if not registration_number:
        if logger:
            logger.debug("No registration_number provided for KBO lookup")
        return kbo_data

    try:
        detailed_results = getattr(response, "detailed_results", None)
        if _is_gettable(detailed_results):
            kbo_enrichment = detailed_results.get("kbo_data") or detailed_results.get(
                "company_registry"
            )
            _apply_kbo_enrichment(kbo_data, kbo_enrichment)
            _apply_loose_registry_fields(kbo_data, detailed_results)

        _apply_request_registry_fields(kbo_data, request)
        _apply_founding_age(kbo_data)
        _mark_success(kbo_data, registration_number, logger)
    except Exception as exc:
        if logger:
            logger.warning(f"Error extracting KBO data: {exc}", exc_info=True)

    return kbo_data


def build_registry_report_context(
    *,
    country_code: str | None,
    registration_number: str | None,
    kbo_data: dict[str, object],
    kvk_registration_label: str,
    kbo_registration_label: str,
    kvk_registry_name: str,
    kbo_registry_name: str,
    business_type_id: str | None = None,
) -> dict[str, object]:
    """Flatten registry enrichment into the main report template contract."""
    is_netherlands = country_code == "NL"
    # Cross-check the manually-selected business type against the registry NACE
    # macro-division so a report can self-disclose when the applied benchmark
    # sector does not match the company's registered activity.
    nace_mismatch = detect_business_type_nace_mismatch(
        business_type_id=business_type_id,
        registry_nace_code=kbo_data.get("kbo_nace_code"),
        registry_nace_description=kbo_data.get("kbo_nace_description"),
    )
    return {
        "country_code": country_code,
        "registration_number_label": (
            kvk_registration_label if is_netherlands else kbo_registration_label
        ),
        "registry_name": kvk_registry_name if is_netherlands else kbo_registry_name,
        "kbo_data": kbo_data,
        "has_kbo_data": bool(kbo_data.get("has_kbo_data", False)),
        "registration_number": registration_number,
        "kbo_number": kbo_data.get("kbo_number"),
        "legal_form": kbo_data.get("legal_form"),
        "legal_form_full": kbo_data.get("legal_form_full"),
        "founding_date": kbo_data.get("founding_date"),
        "founded_year": kbo_data.get("founded_year"),
        "company_age_years": kbo_data.get("company_age_years"),
        "kbo_nace_code": kbo_data.get("kbo_nace_code"),
        "kbo_nace_description": kbo_data.get("kbo_nace_description"),
        "kbo_status": kbo_data.get("kbo_status"),
        "kbo_address": kbo_data.get("kbo_address"),
        "kbo_municipality": kbo_data.get("kbo_municipality"),
        "kbo_postal_code": kbo_data.get("kbo_postal_code"),
        # VZW/ASBL flag: non-profits cannot distribute profits in a standard
        # share-transfer; the valuation methodology and report framing must
        # reflect this fundamentally different M&A premise.  Check both the
        # compact form ("VZW") and the full label ("Vereniging zonder
        # winstoogmerk") — registries populate one or the other.
        "is_vzw": (
            is_vzw_legal_form(kbo_data.get("legal_form"))
            or is_vzw_legal_form(kbo_data.get("legal_form_full"))
        ),
        # NACE vs. selected-business-type cross-check (release-blocker disclosure).
        "nace_business_type_mismatch": nace_mismatch.is_mismatch,
        "nace_mismatch_selected_title": nace_mismatch.selected_business_type_title,
        "nace_mismatch_selected_nace": nace_mismatch.selected_nace_code,
        "nace_mismatch_registry_nace": nace_mismatch.registry_nace_code,
        "nace_mismatch_registry_desc": nace_mismatch.registry_nace_description,
    }
