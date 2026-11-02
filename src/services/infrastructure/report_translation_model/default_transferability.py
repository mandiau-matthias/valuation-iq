"""Default transferability, owner-risk, workflow, and valuation waterfall fields."""

from dataclasses import dataclass
from dataclasses import field
from src.services.infrastructure.report_step_names import CALC_STEP_NAMES_NL as _CALC_STEP_NAMES_NL


@dataclass(frozen=True)
class ReportTranslationDefaultTransferabilityFields:
    """Default transferability, owner-risk, workflow, and valuation waterfall fields."""


