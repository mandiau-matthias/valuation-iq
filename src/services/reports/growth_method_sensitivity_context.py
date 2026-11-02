"""Explicit earnings-growth scenarios tied to a saved, reconciled method basis."""

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal, localcontext

from src.domain.financial_arithmetic import money
from src.services.infrastructure.template_formatter import TemplateFormatter
from src.services.reports.report_value_admission import report_decimal


def saved_growth_multiple_scenario(context: dict[str, object]) -> dict[str, object] | None:
    source = context.get("canonical_multiple_sensitivity")
    if not isinstance(source, Mapping) or source.get("metric_type") != "EBITDA":
        return None
    identity = [
        source.get(key)
        for key in ("source_run_id", "source_run_hash", "currency", "valuation_date")
    ]
    if not all(isinstance(value, str) and value for value in identity):
        return None
    metric = report_decimal(source.get("pricing_metric"), "saved pricing earnings")
    multiple = report_decimal(source.get("effective_multiple"), "saved effective multiple")
    saved_ev = report_decimal(source.get("saved_enterprise_value"), "saved method EV")
    if metric <= 0 or multiple <= 0:
        return None
    locale = str(context.get("locale") or "nl")
    currency = str(source["currency"])
    with localcontext() as arithmetic:
        arithmetic.prec = 100
        if money(metric * multiple) != money(saved_ev):
            return None
        factors = (Decimal(".8"), Decimal("1"), Decimal("1.2"))
        band = [multiple * factor for factor in factors]
        changes = (Decimal("-.03"), Decimal("0"), Decimal(".03"))
        labels = ("Downside", "Basis", "Upside")
        rows = []
        raw_rows = []
        for label, change in zip(labels, changes):
            earnings = metric * (1 + change)
            cells = [money(earnings * applied) for applied in band]
            raw_rows.append(
                {
                    "change": str(change),
                    "earnings": str(earnings),
                    "cells": [str(value) for value in cells],
                }
            )
            rows.append(
                {
                    "label": label,
                    "is_basis": change == 0,
                    "growth": f"{change * 100:.1f}%",
                    "ebitda": TemplateFormatter.format_currency(
                        earnings, currency=currency, locale=locale
                    ),
                    "cells": [
                        TemplateFormatter.format_currency(value, currency=currency, locale=locale)
                        for value in cells
                    ],
                    "exact_earnings": str(earnings),
                    "exact_cells": [str(value) for value in cells],
                }
            )
    descriptor = {
        "schema_version": "report_earnings_growth_sensitivity.v1",
        "kind": "illustrative_sensitivity",
        "statistical_coverage": None,
        "value_basis": "enterprise_value",
        "method_key": "canonical_ebitda_multiple",
        "source_run_id": source["source_run_id"],
        "source_run_hash": source["source_run_hash"],
        "currency": currency,
        "valuation_date": source["valuation_date"],
        "pricing_metric": str(metric),
        "pricing_multiple": str(multiple),
        "saved_enterprise_value": str(saved_ev),
        "earnings_changes": ["-0.03", "0", "0.03"],
        "multiple_factors": ["0.8", "1", "1.2"],
        "held_assumptions": "All other saved method assumptions; no new EV-to-equity bridge; no revenue forecast",
        "rows": raw_rows,
    }
    calculation_id = hashlib.sha256(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "band_labels": [f"≈{value:.4f}×" for value in band],
        "rows": rows,
        "delta_pct": "3.0%",
        "reconciles_to_headline": True,
        "is_hybrid": False,
        "calculation_id": calculation_id,
        "source_run_id": source["source_run_id"],
        "source_run_hash": source["source_run_hash"],
        "currency": currency,
        "scenario": descriptor,
    }


def apply_saved_growth_multiple_scenario(context: dict[str, object]) -> None:
    """Clear stale report-generated scenarios before projecting the saved basis."""
    context["advisor_growth_multiple"] = saved_growth_multiple_scenario(context)
    context["show_growth_multiple_sensitivity"] = (
        str(context.get("report_audience") or "").lower() == "advisor"
        and context["advisor_growth_multiple"] is not None
    )
