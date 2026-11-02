"""Year-data validation rules for legacy valuation requests."""

from __future__ import annotations

from typing import List, Optional

from src.api.routes.valuation.valuation_types import ValidationError


def validate_current_year_data(current_year_data: object) -> List[ValidationError]:
    """Validate current year financial data for non-startup valuation paths."""
    errors: List[ValidationError] = []

    try:
        if not current_year_data:
            errors.append(
                ValidationError(
                    field="current_year_data",
                    message="Current year data is required",
                    value=None,
                )
            )
            return errors

        if not hasattr(current_year_data, "revenue") or current_year_data.revenue <= 0:
            errors.append(
                ValidationError(
                    field="current_year_data.revenue",
                    message="Revenue must be positive",
                    value=getattr(current_year_data, "revenue", None),
                )
            )

        if not hasattr(current_year_data, "ebitda"):
            errors.append(
                ValidationError(
                    field="current_year_data.ebitda",
                    message="EBITDA is required",
                    value=None,
                )
            )

        return errors

    except Exception as e:
        errors.append(
            ValidationError(
                field="current_year_data",
                message=f"Error validating current year data: {str(e)}",
                value=str(current_year_data),
            )
        )
        return errors


def validate_startup_current_year_data(
    current_year_data: object,
    startup_inputs: Optional[object] = None,
) -> List[ValidationError]:
    """Validate current-year data for the pre-revenue startup valuation path."""
    errors: List[ValidationError] = []

    try:
        if not current_year_data:
            errors.append(
                ValidationError(
                    field="current_year_data",
                    message="Current year data is required",
                    value=None,
                )
            )
            return errors

        if not hasattr(current_year_data, "revenue"):
            errors.append(
                ValidationError(
                    field="current_year_data.revenue",
                    message="Revenue is required (use 0 for pre-revenue startups)",
                    value=None,
                )
            )
        else:
            revenue_value = getattr(current_year_data, "revenue", None)
            if revenue_value is not None and revenue_value < 0:
                errors.append(
                    ValidationError(
                        field="current_year_data.revenue",
                        message="Revenue cannot be negative",
                        value=revenue_value,
                    )
                )

        if not hasattr(current_year_data, "ebitda"):
            errors.append(
                ValidationError(
                    field="current_year_data.ebitda",
                    message="EBITDA is required (use 0 if not yet meaningful)",
                    value=None,
                )
            )

        if startup_inputs is None:
            errors.append(
                ValidationError(
                    field="startup_inputs",
                    message=(
                        "selected_method='startup_valuation' requires the "
                        "'startup_inputs' block (qualitative sliders, "
                        "traction, cap-table)."
                    ),
                    value=None,
                )
            )

        return errors

    except Exception as e:  # pragma: no cover - defensive
        errors.append(
            ValidationError(
                field="current_year_data",
                message=f"Error validating startup current year data: {str(e)}",
                value=str(current_year_data),
            )
        )
        return errors


def validate_ebitda_only_current_year_data(current_year_data: object) -> List[ValidationError]:
    """Validate current-year data for the EBITDA-only multiples path.

    For abbreviated / "gross_margin" filers (roughly half of Belgian SME accounts) turnover is
    not disclosed but filed EBITDA is real. The standard non-startup validator hard-rejects
    these with "Revenue must be positive". This permissive variant is reached ONLY when the
    request explicitly selects an EV/EBITDA multiple (``selected_method`` normalises to
    ``ebitda_multiple``); it drops the positive-revenue requirement but REQUIRES positive
    EBITDA -- the actual basis of value on this path -- so we never price a company with no
    earnings. A present revenue must not be negative.
    """
    errors: List[ValidationError] = []

    try:
        if not current_year_data:
            errors.append(
                ValidationError(
                    field="current_year_data",
                    message="Current year data is required",
                    value=None,
                )
            )
            return errors

        ebitda = getattr(current_year_data, "ebitda", None)
        if ebitda is None:
            errors.append(
                ValidationError(
                    field="current_year_data.ebitda",
                    message="EBITDA is required for the EBITDA-multiple path",
                    value=None,
                )
            )
        elif ebitda <= 0:
            errors.append(
                ValidationError(
                    field="current_year_data.ebitda",
                    message=(
                        "EBITDA must be positive for the EBITDA-multiple path "
                        "(no positive earnings to apply a multiple to)"
                    ),
                    value=ebitda,
                )
            )

        revenue = getattr(current_year_data, "revenue", None)
        if revenue is not None and revenue < 0:
            errors.append(
                ValidationError(
                    field="current_year_data.revenue",
                    message="Revenue cannot be negative",
                    value=revenue,
                )
            )

        return errors

    except Exception as e:  # pragma: no cover - defensive
        errors.append(
            ValidationError(
                field="current_year_data",
                message=f"Error validating EBITDA-only current year data: {str(e)}",
                value=str(current_year_data),
            )
        )
        return errors


def validate_ebitda_only_historical_data(historical_data: object) -> List[ValidationError]:
    """Validate historical rows for the EBITDA-only multiples path.

    Same as :func:`validate_historical_data` but revenue is OPTIONAL per row (abbreviated
    filers disclose no turnover). Only the year is required; a present revenue must not be
    negative. Historical rows are not the basis of value on this path (the headline is priced
    on the latest filed EBITDA), so this is deliberately permissive.
    """
    errors: List[ValidationError] = []

    try:
        if not historical_data:
            return errors

        for i, year_data in enumerate(historical_data):
            if not hasattr(year_data, "year"):
                errors.append(
                    ValidationError(
                        field=f"historical_years_data[{i}]",
                        message="Year is required for historical data",
                        value=str(year_data),
                    )
                )
                continue

            revenue = getattr(year_data, "revenue", None)
            if revenue is not None and revenue < 0:
                errors.append(
                    ValidationError(
                        field=f"historical_years_data[{i}].revenue",
                        message="Historical revenue cannot be negative",
                        value=revenue,
                    )
                )

        return errors

    except Exception as e:  # pragma: no cover - defensive
        errors.append(
            ValidationError(
                field="historical_years_data",
                message=f"Error validating EBITDA-only historical data: {str(e)}",
                value=str(historical_data),
            )
        )
        return errors


def validate_historical_data(historical_data: object) -> List[ValidationError]:
    """Validate historical financial rows for legacy valuation requests."""
    errors: List[ValidationError] = []

    try:
        if not historical_data:
            return errors

        for i, year_data in enumerate(historical_data):
            if not hasattr(year_data, "year") or not hasattr(year_data, "revenue"):
                errors.append(
                    ValidationError(
                        field=f"historical_years_data[{i}]",
                        message="Year and revenue are required for historical data",
                        value=str(year_data),
                    )
                )
                continue

            if year_data.revenue <= 0:
                errors.append(
                    ValidationError(
                        field=f"historical_years_data[{i}].revenue",
                        message="Historical revenue must be positive",
                        value=year_data.revenue,
                    )
                )

        return errors

    except Exception as e:
        errors.append(
            ValidationError(
                field="historical_years_data",
                message=f"Error validating historical data: {str(e)}",
                value=str(historical_data),
            )
        )
        return errors
