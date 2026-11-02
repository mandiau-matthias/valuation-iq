"""Numeric bounds validation for valuation requests."""


def validate_numeric_bounds(request, validation_error_cls) -> list:
    """Validate numeric values are within reasonable bounds to prevent DoS."""
    errors = []

    if not request.current_year_data:
        return errors

    current_data = request.current_year_data

    if current_data.revenue is not None:
        if current_data.revenue < 0:
            errors.append(
                validation_error_cls(
                    field="current_year_data.revenue",
                    message="Revenue cannot be negative",
                    value=current_data.revenue,
                    constraint="Revenue >= 0",
                )
            )
        elif current_data.revenue > 10_000_000_000_000:
            errors.append(
                validation_error_cls(
                    field="current_year_data.revenue",
                    message=(
                        f"Revenue value (€{current_data.revenue:,.0f}) exceeds reasonable "
                        "bounds. Please verify."
                    ),
                    value=current_data.revenue,
                    constraint="Revenue <= €10 trillion",
                )
            )

    if current_data.ebitda is not None:
        if current_data.ebitda < -1_000_000_000_000:
            errors.append(
                validation_error_cls(
                    field="current_year_data.ebitda",
                    message=f"EBITDA value (€{current_data.ebitda:,.0f}) is unreasonably negative",
                    value=current_data.ebitda,
                    constraint="EBITDA >= -€1 trillion",
                )
            )
        elif current_data.ebitda > 1_000_000_000_000:
            errors.append(
                validation_error_cls(
                    field="current_year_data.ebitda",
                    message=f"EBITDA value (€{current_data.ebitda:,.0f}) exceeds reasonable bounds",
                    value=current_data.ebitda,
                    constraint="EBITDA <= €1 trillion",
                )
            )

    num_employees = getattr(request, "number_of_employees", None)
    if num_employees is not None and num_employees > 10_000_000:
        errors.append(
            validation_error_cls(
                field="number_of_employees",
                message=f"Number of employees ({num_employees:,}) exceeds reasonable bounds",
                value=num_employees,
                constraint="Employees <= 10 million",
            )
        )

    num_owners = getattr(request, "number_of_owners", None)
    if num_owners is not None and num_owners > 1_000_000:
        errors.append(
            validation_error_cls(
                field="number_of_owners",
                message=f"Number of owners ({num_owners:,}) exceeds reasonable bounds",
                value=num_owners,
                constraint="Owners <= 1 million",
            )
        )

    if request.historical_years_data and len(request.historical_years_data) > 100:
        errors.append(
            validation_error_cls(
                field="historical_years_data",
                message=(
                    f"Too many historical years ({len(request.historical_years_data)}). "
                    "Maximum 100 years allowed."
                ),
                value=len(request.historical_years_data),
                constraint="Historical years <= 100",
            )
        )

    if request.company_name and len(request.company_name) > 500:
        errors.append(
            validation_error_cls(
                field="company_name",
                message=(
                    f"Company name too long ({len(request.company_name)} characters). "
                    "Maximum 500 characters allowed."
                ),
                value=len(request.company_name),
                constraint="Company name <= 500 characters",
            )
        )

    return errors
