"""Request/response context helpers for the simplified report transformer."""

from decimal import Decimal
from typing import Dict, Optional

from src.api.schemas import ValuationRequest, ValuationResponse
from src.domain.report_contact.sanitize import sanitize_report_email, sanitize_report_phone
from src.domain.valuation_contract import normalize_method_key


def get_request_metadata(request: Optional[ValuationRequest]) -> Optional[Dict[str, object]]:
    """Return request metadata only when it is a mapping."""
    if not request or not hasattr(request, "metadata"):
        return None
    metadata = getattr(request, "metadata", None)
    return metadata if isinstance(metadata, dict) else None


def selected_method_is_startup_valuation(request: Optional[ValuationRequest]) -> bool:
    """Match main report aggregation: venture path must not apply SME weighted synthesis."""
    if not request:
        return False
    metadata = get_request_metadata(request) or {}
    selected_method = getattr(request, "selected_method", None) or metadata.get("selected_method")
    return str(normalize_method_key(selected_method)) == "startup_valuation"


def get_industry(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Optional[str]:
    """Get normalized industry from request or response."""
    request_industry = getattr(request, "industry", None) if request else None
    if request_industry:
        return str(request_industry).title().replace("_", " ").replace("-", " ")

    if response.detailed_results:
        industry = response.detailed_results.get("industry")
        if industry:
            return str(industry).title().replace("_", " ").replace("-", " ")

    return None


def get_industry_emoji(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Optional[str]:
    """Get industry emoji based on industry name."""
    industry = get_industry(response, request)
    if not industry:
        return None

    industry_lower = industry.lower()
    emoji_map = {
        "bakkerij": "🥐",
        "bakery": "🥐",
        "restaurant": "🍽️",
        "food": "🍽️",
        "hospitality": "🍽️",
        "catering": "🍽️",
        "tech": "💻",
        "software": "💻",
        "it ": "💻",
        "digital": "💻",
        "saas": "☁️",
        "cloud": "☁️",
        "retail": "🛒",
        "store": "🛒",
        "shop": "🛒",
        "ecommerce": "📦",
        "e-commerce": "📦",
        "manufacturing": "🏭",
        "industrial": "🏭",
        "production": "🏭",
        "logistics": "🚚",
        "transport": "🚚",
        "shipping": "🚚",
        "healthcare": "🏥",
        "medical": "🏥",
        "pharma": "💊",
        "education": "📚",
        "training": "📚",
        "school": "📚",
        "real estate": "🏠",
        "property": "🏠",
        "finance": "💰",
        "banking": "🏦",
        "insurance": "📊",
        "construction": "🏗️",
        "building": "🏗️",
        "energy": "⚡",
        "power": "⚡",
        "solar": "☀️",
        "creative": "🎨",
        "media": "🎬",
        "advertising": "📢",
        "services": "💼",
        "consulting": "💼",
        "professional": "💼",
        "agriculture": "🌾",
        "farm": "🌾",
    }

    for keyword, emoji in emoji_map.items():
        if keyword in industry_lower:
            return emoji

    return "🏢"


def get_revenue(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Optional[Decimal]:
    """Get revenue from response or request."""
    response_year_data = getattr(response, "current_year_data", None)
    if response_year_data and hasattr(response_year_data, "revenue"):
        revenue = _decimal_or_none(getattr(response_year_data, "revenue", None))
        if revenue is not None:
            return revenue

    request_year_data = getattr(request, "current_year_data", None) if request else None
    if request_year_data and hasattr(request_year_data, "revenue"):
        return _decimal_or_none(getattr(request_year_data, "revenue", None))

    return None


def _decimal_or_none(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None


def get_accountant_name(request: Optional[ValuationRequest]) -> Optional[str]:
    """Get accountant/advisor firm name from request metadata."""
    metadata = get_request_metadata(request)
    if metadata is None:
        return None
    value = metadata.get("accountant_firm_name")
    return str(value).strip() if value is not None else None


def get_accountant_logo(request: Optional[ValuationRequest]) -> Optional[str]:
    """Get accountant logo URL from request metadata."""
    metadata = get_request_metadata(request)
    if metadata is None:
        return None
    value = metadata.get("accountant_logo_url")
    return str(value).strip() if value is not None else None


def get_accountant_email(request: Optional[ValuationRequest]) -> Optional[str]:
    """Get sanitized accountant email from request metadata."""
    metadata = get_request_metadata(request)
    if metadata is None:
        return None
    value = metadata.get("accountant_email")
    if value is None:
        return None
    sanitized = sanitize_report_email(str(value).strip())
    return sanitized if isinstance(sanitized, str) else None


def get_accountant_phone(request: Optional[ValuationRequest]) -> Optional[str]:
    """Get sanitized accountant phone from request metadata."""
    metadata = get_request_metadata(request)
    if metadata is None:
        return None
    value = metadata.get("accountant_phone")
    if value is None:
        return None
    sanitized = sanitize_report_phone(str(value).strip())
    return sanitized if isinstance(sanitized, str) else None
