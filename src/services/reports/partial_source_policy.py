"""Server-selected admission for partial inputs without authenticated sources."""

from typing import cast

from src.api.schemas.partial_valuation import PartialValuationResponse
from src.api.schemas.stateless_response_schemas import MethodResult
from src.services.reports.stateless_valuation_run import canonical_hash

SOURCE_REQUIRED = (
    "Verified source evidence is required. Supplied amounts, references and advisor "
    "assumptions remain diagnostic scenarios outside published valuation methods."
)
FORECAST_REQUIRED = (
    "A verified company forecast or cash-flow schedule is required for priced DCF. "
    "An advisor assumption or raw upload does not establish source verification."
)


def seal_unverified_assessment(
    scenario: PartialValuationResponse,
) -> PartialValuationResponse:
    fields = scenario.model_dump(mode="json", exclude={"assessment_id", "content_sha256"})
    fields["schema_version"] = "partial_valuation.v3"
    fields["source_policy_version"] = "source-evidence-required.v1"
    fields["conclusion"] = "no_numerical_basis"
    fields["diagnostics"] = {
        key: method.model_copy(
            update={"available": False, "unavailable_reason": SOURCE_REQUIRED}
        ).model_dump(mode="json")
        for key, method in scenario.methods.items()
        if method.value is not None or method.enterprise_value is not None
    }
    fields["methods"] = {
        key: MethodResult(
            method_key=method.method_key,
            label=method.label,
            available=False,
            value=None,
            unavailable_reason=FORECAST_REQUIRED if key == "dcf" else SOURCE_REQUIRED,
        ).model_dump(mode="json")
        for key, method in scenario.methods.items()
    }
    # Arithmetic explanations belong to diagnostics, not the published method
    # disclosures. Inputs and diagnostic outputs remain sealed for review.
    fields["assumptions"] = [SOURCE_REQUIRED, FORECAST_REQUIRED]
    digest = canonical_hash(fields)
    return cast(
        PartialValuationResponse,
        PartialValuationResponse.model_validate(
            dict(fields, content_sha256=digest, assessment_id=f"partial_{digest}")
        ),
    )
