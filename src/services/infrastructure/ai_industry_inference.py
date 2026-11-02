"""
Deterministic Industry and Business Model Inference

Uses local classification helpers to infer:
- Industry code (for valuation multiples)
- Business model (for premiums/adjustments)

Privacy: Only uses PUBLIC company data (name, legal form, activity description)
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from .classification_helpers import classify_industry_and_model


class IndustryInference(BaseModel):
    """Locally inferred industry and business model."""

    industry: str  # technology, retail, services, healthcare, etc.
    business_model: str  # b2b_saas, b2c, marketplace, ecommerce, services, other
    confidence: Decimal  # Decimal('0.0') to Decimal('1.0')
    reasoning: str  # Why this classification


async def infer_industry_and_model(
    company_name: str,
    legal_form: Optional[str] = None,
    primary_activity_code: Optional[str] = None,
    primary_activity_description: Optional[str] = None,
    website: Optional[str] = None,
) -> IndustryInference:
    """
    Infer industry and business model from company data.

    Uses classification helpers only. AI orchestration lives in Titan.
    """
    industry, business_model = classify_industry_and_model(
        primary_activity_code,
        primary_activity_description,
    )
    return IndustryInference(
        industry=industry,
        business_model=business_model,
        confidence=Decimal("0.8"),
        reasoning=f"Inferred from activity: {primary_activity_description or 'N/A'}",
    )
