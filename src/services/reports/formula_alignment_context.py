"""Read-only financial basis projection for report formulas.

An EV/metric ratio is not an observed earnings record. Financial discrepancies
must survive rendering for validation, never be hidden by back-solving a metric
or replacing the saved conclusion with metric × multiple.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, TypeAlias

from src.services.reports.report_value_admission import admitted_band

ReportMap: TypeAlias = dict[str, object]


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...
    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class FormulaAlignmentResult:
    metric_type: str
    metric_value: Decimal
    enterprise_value_low: Decimal
    enterprise_value_mid: Decimal
    enterprise_value_high: Decimal


def align_formula_context(
    *,
    step_data: ReportMap,
    multiple_context: ReportMap,
    revenue_value: Decimal,
    sustainable_ebitda: Decimal,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    applied_multiple: Decimal,
    multiple_low: Decimal,
    multiple_high: Decimal,
    is_dcf_only: bool,
    is_asset_anchored: bool,
    is_weighted_synthesis: bool = False,
    logger: LoggerLike | None = None,
) -> FormulaAlignmentResult:
    """Select the supplied earnings definition and preserve the admitted EV band."""
    metric_type = str(multiple_context["metric_type"])
    metric = revenue_value if metric_type == "REVENUE" else sustainable_ebitda
    low, mid, high = admitted_band(
        enterprise_value_low, enterprise_value_mid, enterprise_value_high
    )
    return FormulaAlignmentResult(metric_type, metric, low, mid, high)
