"""Years-of-data extraction for defensibility classification."""

from typing import Optional

JsonMap = dict[str, object]


def _count_historical_years(rows: object) -> int:
    if not isinstance(rows, list):
        return 0
    count = 0
    for row in rows:
        is_forecast = (
            bool(row.get("is_forecast"))
            if isinstance(row, dict)
            else bool(getattr(row, "is_forecast", False))
        )
        if not is_forecast:
            count += 1
    return count


def _year_data_rows(rows: object) -> list[JsonMap]:
    if isinstance(rows, dict):
        year_rows: list[JsonMap] = []
        for key, value in rows.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("year", key)
                year_rows.append(row)
            else:
                year_rows.append({"year": key, "value": value})
        return year_rows
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _count_year_data_entries(rows: object) -> int:
    """Count unique non-forecast years in ``year_data`` payloads."""
    years: set[int] = set()
    for row in _year_data_rows(rows):
        if bool(row.get("is_forecast")):
            continue
        raw_year = row.get("year") or row.get("fiscal_year")
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            continue
        if year > 0:
            years.add(year)
    return len(years)


def _has_current_year(container: JsonMap, include_flattened: bool = True) -> bool:
    if "current_year_data" in container and container.get("current_year_data") is not None:
        return True
    if not include_flattened:
        return False
    return any(container.get(key) is not None for key in ("revenue", "ebitda", "net_income"))


def _to_non_negative_int(value: object) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        integer_value = int(value)
    except (TypeError, ValueError):
        return None
    return integer_value if integer_value >= 0 else None


def _extract_step_zero_result(step_results: object) -> Optional[JsonMap]:
    if not isinstance(step_results, dict):
        return None
    for key in (0, 0.0, "0"):
        step_0 = step_results.get(key)
        if step_0 is None:
            continue
        step_result = (
            step_0.get("result") if isinstance(step_0, dict) else getattr(step_0, "result", None)
        )
        if isinstance(step_result, dict):
            return step_result
    return None


def _explicit_years_from_container(container: JsonMap) -> Optional[int]:
    years = _to_non_negative_int(container.get("years_of_data"))
    if years is None:
        years = _to_non_negative_int(container.get("data_years"))
    return years if years is not None and years > 0 else None


def _derived_years_from_container(container: JsonMap) -> Optional[int]:
    hist_count = _to_non_negative_int(container.get("historical_years_count"))
    if hist_count is not None:
        return hist_count + (1 if _has_current_year(container) else 0)

    year_data_count = _count_year_data_entries(container.get("year_data"))
    if year_data_count > 0:
        return year_data_count

    step_zero_result = _extract_step_zero_result(container.get("step_results"))
    if step_zero_result is None:
        return None
    nested_years = _extract_from_container(step_zero_result)
    return nested_years if nested_years is not None and nested_years > 0 else None


def _extract_from_container(container: JsonMap) -> Optional[int]:
    return _explicit_years_from_container(container) or _derived_years_from_container(container)


def extract_years_of_data(valuation_data: object) -> int:
    """Count historical + current-year financial records deterministically.

    Priority order:
      1. Explicit engine-computed year counters (``years_of_data`` / ``data_years``)
      2. Explicit historical counter + current-year presence
      3. Derived count from ``year_data`` or nested Step 0 result
      4. Derived count from historical rows plus explicit current-year block
      5. Last-resort flattened current-year inference
    """
    if not isinstance(valuation_data, dict):
        return 0

    detailed = valuation_data.get("detailed_results")
    for container in (detailed if isinstance(detailed, dict) else None, valuation_data):
        if not isinstance(container, dict):
            continue
        years = _extract_from_container(container)
        if years is not None and years > 0:
            return years

    hist_count = _count_historical_years(valuation_data.get("historical_years_data"))
    has_current_explicit = _has_current_year(valuation_data, include_flattened=False)
    direct_years = hist_count + (1 if has_current_explicit else 0)
    if direct_years > 0:
        return direct_years

    year_data_count = _count_year_data_entries(valuation_data.get("year_data"))
    if year_data_count > 0:
        return year_data_count

    return 1 if _has_current_year(valuation_data, include_flattened=True) else 0
