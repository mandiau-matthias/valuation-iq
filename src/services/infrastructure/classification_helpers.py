"""
Industry and Business Model Classification Helpers

Extracted from ai_industry_inference.py to reduce complexity.
These helpers classify industries and business models using simple heuristics.
"""

from typing import Optional


def classify_industry(activity_description: Optional[str]) -> str:
    """
    Classify industry from activity description.
    
    Args:
        activity_description: Activity description from KBO
        
    Returns:
        Industry classification (technology, retail, manufacturing, etc.)
    """
    if not activity_description:
        return "other"
    
    desc_lower = activity_description.lower()
    
    # Technology
    if any(keyword in desc_lower for keyword in ["software", "it ", "computer"]):
        return "technology"
    
    # Retail
    if any(keyword in desc_lower for keyword in ["retail", "shop", "store"]):
        return "retail"
    
    # Manufacturing
    if any(keyword in desc_lower for keyword in ["manufacturing", "production"]):
        return "manufacturing"
    
    # Healthcare
    if any(keyword in desc_lower for keyword in ["healthcare", "medical"]):
        return "healthcare"
    
    # Finance
    if any(keyword in desc_lower for keyword in ["finance", "bank", "insurance"]):
        return "finance"
    
    # Construction
    if any(keyword in desc_lower for keyword in ["construction", "building"]):
        return "construction"
    
    # Hospitality
    if any(keyword in desc_lower for keyword in ["hotel", "restaurant", "tourism"]):
        return "hospitality"
    
    # Real Estate
    if any(keyword in desc_lower for keyword in ["real estate", "property"]):
        return "real_estate"
    
    # Services
    if any(keyword in desc_lower for keyword in ["consulting", "advisory", "services"]):
        return "services"
    
    return "other"


def classify_business_model(activity_description: Optional[str], industry: str) -> str:
    """
    Classify business model from activity description and industry.
    
    Args:
        activity_description: Activity description from KBO
        industry: Industry classification
        
    Returns:
        Business model classification (b2b_saas, b2c, marketplace, etc.)
    """
    if not activity_description:
        return "other"
    
    desc_lower = activity_description.lower()
    
    # B2B SaaS
    if any(keyword in desc_lower for keyword in ["saas", "subscription"]):
        return "b2b_saas"
    
    # Marketplace
    if any(keyword in desc_lower for keyword in ["marketplace", "platform"]):
        return "marketplace"
    
    # E-commerce
    if "e-commerce" in desc_lower or ("online" in desc_lower and "retail" in desc_lower):
        return "ecommerce"
    
    # Manufacturing
    if "manufacturing" in desc_lower:
        return "manufacturing"
    
    # B2C
    if any(keyword in desc_lower for keyword in ["b2c", "consumer"]):
        return "b2c"
    
    # Services fallback
    if industry == "services":
        return "services"
    
    return "other"


def classify_industry_and_model(
    nace_code: Optional[str],
    activity_description: Optional[str]
) -> tuple[str, str]:
    """
    Classify both industry and business model from activity description.
    
    This is the refactored version of _fallback_classification that reduces
    complexity from 50 to ~5 by extracting classification logic into separate functions.
    
    Args:
        nace_code: NACE code (not currently used, reserved for future)
        activity_description: Activity description from KBO
        
    Returns:
        Tuple of (industry, business_model)
    """
    industry = classify_industry(activity_description)
    business_model = classify_business_model(activity_description, industry)
    
    return industry, business_model

