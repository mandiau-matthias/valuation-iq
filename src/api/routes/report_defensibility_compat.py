"""Backward-compatible defensibility helpers for report routes."""

JsonMap = dict[str, object]


def _classify_valuation_data(valuation_data: JsonMap, locale: str = "nl"):
    """Legacy 5-tuple return: ``(classification, [], cap, auto, banner)``."""
    from src.services.defensibility import build_defensibility_banner
    from src.services.defensibility import classify_valuation_data as _modular_classify
    from src.services.infrastructure.report_classifier import ReportClassification
    from src.services.infrastructure.translations import normalize_report_locale

    loc = normalize_report_locale(locale)
    verdict = _modular_classify(valuation_data, locale=loc)

    classification = None
    if verdict.classification_value is not None:
        for candidate in ReportClassification:
            if candidate.value == verdict.classification_value:
                classification = candidate
                break

    banner = None
    if verdict.auto_watermark:
        banner = build_defensibility_banner(
            classification_value=verdict.classification_value,
            confidence_cap=verdict.confidence_cap,
            cap_reason=verdict.cap_reason,
            margin_warning=verdict.margin_warning,
            engine_signals=verdict.engine_signals,
            locale=loc,
            is_full_report=verdict.is_full_report,
            show_confidence_cap=True,
        )

    return classification, [], verdict.confidence_cap, verdict.auto_watermark, banner


def _apply_classification_to_asking_price(context: JsonMap, valuation_data: JsonMap) -> None:
    """Backward-compatible shim; delegates to the modular gate."""
    from src.services.defensibility import apply_asking_price_gate

    apply_asking_price_gate(context, valuation_data)
