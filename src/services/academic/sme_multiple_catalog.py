"""Static SME multiple calibration catalog."""

from __future__ import annotations

from decimal import Decimal

# SME Classification thresholds (based on European Commission + academic sources)
MICRO_SME_THRESHOLD = Decimal("500000")  # < €500K revenue
SMALL_SME_THRESHOLD = Decimal("5000000")  # €500K - €5M revenue
MEDIUM_SME_THRESHOLD = Decimal("50000000")  # €5M - €50M revenue

# ACADEMIC VALIDATION BOUNDS (Pepperdine 2024, VFB Belgium 2024)
# These bounds prevent outlier multiples that would indicate data issues
# Based on 99th percentile of actual SME transactions
SME_MULTIPLE_BOUNDS = {
    "micro": {
        "ebitda_min": Decimal("1.5"),  # Floor: distressed/liquidation value
        "ebitda_max": Decimal("5.0"),  # Ceiling: exceptional micro SME (BizBuySell 99th pctile)
        "revenue_min": Decimal("0.2"),
        "revenue_max": Decimal("2.0"),
    },
    "small": {
        "ebitda_min": Decimal("2.0"),
        "ebitda_max": Decimal("6.5"),  # Ceiling: Pepperdine 2024 99th pctile for small SME
        "revenue_min": Decimal("0.3"),
        "revenue_max": Decimal("2.5"),
    },
    "medium": {
        "ebitda_min": Decimal("2.5"),
        "ebitda_max": Decimal("10.0"),  # Raised for Delphi 2.0: SaaS/tech SMEs can reach 10x
        "revenue_min": Decimal("0.5"),
        "revenue_max": Decimal("4.5"),  # Raised for SaaS EV/Revenue multiples
    },
}

# Industry-specific ceiling overrides for EBITDA multiples.
# Professional services (accounting, consulting, legal) trade at higher
# multiples due to recurring client relationships and high margins.
# Sources: Pepperdine 2024 professional services sub-report, IBBA 2024.
# Industry-specific ceiling overrides for SME_MULTIPLE_BOUNDS validation.
# Values aligned with SME_EBITDA_CAPS in populate_sme_calibration_columns.py
# and BELGIAN_SME_MULTIPLES above. Sources: VFB Belgium 2024, Pepperdine 2024.
EBITDA_MAX_INDUSTRY_OVERRIDES = {
    "professional-services": {
        "micro": Decimal("5.5"),
        "small": Decimal("7.0"),
        "medium": Decimal("8.5"),
    },
    "services": {"micro": Decimal("5.0"), "small": Decimal("6.5"), "medium": Decimal("8.0")},
    "consulting": {"micro": Decimal("5.0"), "small": Decimal("6.5"), "medium": Decimal("8.0")},
    "healthcare": {"micro": Decimal("5.5"), "small": Decimal("7.0"), "medium": Decimal("9.0")},
    "technology": {"micro": Decimal("6.0"), "small": Decimal("8.5"), "medium": Decimal("10.5")},
    "tech-digital": {"micro": Decimal("6.0"), "small": Decimal("8.5"), "medium": Decimal("10.5")},
    "financial-services": {
        "micro": Decimal("5.5"),
        "small": Decimal("7.0"),
        "medium": Decimal("9.0"),
    },
    "environmental": {"micro": Decimal("4.0"), "small": Decimal("5.5"), "medium": Decimal("7.5")},
}

# Maps business-type categories (from synced_business_types.json) and common
# industry strings to canonical SME-multiple keys. This replaces fragile
# substring matching with deterministic lookups.
CATEGORY_TO_SME_KEY = {
    # Direct category matches (from business_types DB)
    "tech-digital": "technology",
    "professional-services": "consulting",
    "food-beverage": "food-beverage",
    "beauty-wellness": "beauty-wellness",
    "home-property": "home-property",
    "hospitality-tourism": "hospitality-tourism",
    "creative-media": "creative-media",
    "education-training": "education-training",
    "events-entertainment": "events-entertainment",
    "financial-services": "financial-services",
    "fitness-health": "fitness-health",
    "pet-services": "pet-services",
    "automotive": "automotive",
    "transportation-logistics": "transportation-logistics",
    "ecommerce-retail": "retail",
    "agriculture": "agriculture",
    "arts-crafts": "arts-crafts",
    "repair-maintenance": "repair-maintenance",
    "environmental": "environmental",
    "security-safety": "security-safety",
    "manufacturing": "manufacturing",
    # Common industry string aliases
    "technology": "technology",
    "saas": "technology",
    "software": "technology",
    "it": "technology",
    "services": "services",
    "professional services": "consulting",
    "professional-services": "consulting",
    "consulting": "consulting",
    "retail": "retail",
    "healthcare": "healthcare",
    "health": "healthcare",
    "medical": "healthcare",
    "manufacturing": "manufacturing",
    "construction": "home-property",
    "food": "food-beverage",
    "restaurant": "food-beverage",
    "restaurants": "food-beverage",
    "food_beverage": "food-beverage",
    "food-beverage": "food-beverage",
    "hospitality": "hospitality-tourism",
    "tourism": "hospitality-tourism",
    "hotel": "hospitality-tourism",
    "finance": "financial-services",
    "financial": "financial-services",
    "lending": "financial-services",
    "fintech": "financial-services",
    "fintech-lending": "financial-services",
    "education": "education-training",
    "training": "education-training",
    "media": "creative-media",
    "creative": "creative-media",
    "entertainment": "events-entertainment",
    "events": "events-entertainment",
    "fitness": "fitness-health",
    "wellness": "beauty-wellness",
    "beauty": "beauty-wellness",
    "pet": "pet-services",
    "auto": "automotive",
    "transport": "transportation-logistics",
    "logistics": "transportation-logistics",
    "agriculture": "agriculture",
    "farming": "agriculture",
    "environmental": "environmental",
    "security": "security-safety",
    "repair": "repair-maintenance",
}

# ══════════════════════════════════════════════════════════════════════
# DELPHI 2.0: Per-business-type Belgian/Benelux SME EBITDA Multiples
#
# Sources: Brookz Overname Barometer 2024, Vlerick/Moore M&A Monitor 2023,
# BDO Belgium M&A Monitor 2024, Marktlink SME Multiples 2024,
# UNIZO/UCM sector federations, NBB/BNB Central Balance Sheet Office.
#
# 173 specific business types with micro/small/medium tiers.
# Replaces the previous 21-category approach which forced lossy mapping
# (e.g., all food businesses → single "food-beverage" multiple).
# ══════════════════════════════════════════════════════════════════════

# fmt: off
BELGIAN_SME_MULTIPLES_BY_TYPE = {
    # FOOD & BEVERAGE — Brookz Horeca baseline 3.5x
    'restaurant':       {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'bakery':           {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'bar-pub':          {'micro': Decimal('2.3'), 'small': Decimal('3.3'), 'medium': Decimal('4.2')},
    'brewery':          {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('6.0')},
    'butcher':          {'micro': Decimal('2.0'), 'small': Decimal('2.8'), 'medium': Decimal('3.5')},
    'catering':         {'micro': Decimal('2.2'), 'small': Decimal('3.2'), 'medium': Decimal('4.2')},
    'chef':             {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'coffee-shop':      {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'food-distribution':{'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'food-truck':       {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'grocery-specialty': {'micro': Decimal('2.3'), 'small': Decimal('3.2'), 'medium': Decimal('4.0')},
    'ice-cream':        {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'juice-bar':        {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('3.8')},
    'meals':            {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'winery':           {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},

    # PROFESSIONAL SERVICES — BDO Belgium avg 5.5x
    'accounting':       {'micro': Decimal('4.0'), 'small': Decimal('5.5'), 'medium': Decimal('7.0')},
    'bookkeeping':      {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'business-brokerage': {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'consulting':       {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'hr':               {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'legal':            {'micro': Decimal('3.8'), 'small': Decimal('5.5'), 'medium': Decimal('7.0')},
    'market-research':  {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'notary':           {'micro': Decimal('5.0'), 'small': Decimal('6.5'), 'medium': Decimal('8.0')},
    'payroll':          {'micro': Decimal('4.2'), 'small': Decimal('6.0'), 'medium': Decimal('7.5')},
    'public-relations': {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'translation':      {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'virtual-assistant': {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},

    # TECH & DIGITAL — Marktlink Tech baseline 6.5x
    'ai-ml':            {'micro': Decimal('5.0'), 'small': Decimal('7.0'), 'medium': Decimal('9.0')},
    'blockchain':       {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'cloud-services':   {'micro': Decimal('5.0'), 'small': Decimal('7.0'), 'medium': Decimal('9.0')},
    'computer-repair':  {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'cybersecurity':    {'micro': Decimal('5.5'), 'small': Decimal('7.5'), 'medium': Decimal('9.5')},
    'data-analytics':   {'micro': Decimal('4.5'), 'small': Decimal('6.5'), 'medium': Decimal('8.5')},
    'game-development': {'micro': Decimal('3.0'), 'small': Decimal('4.5'), 'medium': Decimal('6.0')},
    'itsupport':        {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'mobile-app':       {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'saas':             {'micro': Decimal('5.5'), 'small': Decimal('8.0'), 'medium': Decimal('10.0')},
    'seo-services':     {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'software':         {'micro': Decimal('5.0'), 'small': Decimal('7.0'), 'medium': Decimal('9.0')},
    'tech-training':    {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'ui-ux-design':     {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'webdev':           {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('6.0')},

    # HEALTHCARE & FITNESS — Vlerick Healthcare avg 6.0x
    'chiropractic':     {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'dental':           {'micro': Decimal('3.8'), 'small': Decimal('5.5'), 'medium': Decimal('7.0')},
    'gym':              {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'healthcare':       {'micro': Decimal('4.2'), 'small': Decimal('6.0'), 'medium': Decimal('7.5')},
    'home-health':      {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'martial-arts':     {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'medical-device':   {'micro': Decimal('4.2'), 'small': Decimal('6.0'), 'medium': Decimal('7.5')},
    'mental-health':    {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'nutrition-counseling': {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'optometry':        {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'personaltraining': {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'physical-therapy': {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'pilates-studio':   {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'telemedicine':     {'micro': Decimal('3.8'), 'small': Decimal('5.5'), 'medium': Decimal('7.0')},
    'veterinary':       {'micro': Decimal('4.2'), 'small': Decimal('6.0'), 'medium': Decimal('7.5')},
    'yoga-studio':      {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},

    # BEAUTY & WELLNESS — Brookz personal services baseline 3.5x
    'barber-shop':      {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'beauty-supply':    {'micro': Decimal('2.3'), 'small': Decimal('3.2'), 'medium': Decimal('4.0')},
    'hairstyling':      {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'makeup':           {'micro': Decimal('2.0'), 'small': Decimal('2.8'), 'medium': Decimal('3.5')},
    'massage':          {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'nail-salon':       {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('3.8')},
    'piercing-studio':  {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'skincare-clinic':  {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'spa':              {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'tanning-salon':    {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'tattoo-parlor':    {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'wellness':         {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},

    # HOME & PROPERTY — Brookz construction/home avg 4.0x
    'cleaning':         {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'construction':     {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'electrical':       {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'hvac':             {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'interior-design':  {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'landscaping':      {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'painting':         {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'plumbing':         {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'realestate':       {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'roofing':          {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},

    # MANUFACTURING — Vlerick/Moore industrial avg 5.0x
    'electronics-manufacturing': {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'general-manufacturing':     {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'metal-fabrication':         {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'plastics-manufacturing':    {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'textile-manufacturing':     {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},

    # ECOMMERCE & RETAIL — Brookz retail baseline 3.8x
    'affiliate-marketing': {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'bookstore':        {'micro': Decimal('2.0'), 'small': Decimal('2.8'), 'medium': Decimal('3.5')},
    'clothing-store':   {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'digital-products': {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'dropshipping':     {'micro': Decimal('2.0'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'ecommerce':        {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'gift-shop':        {'micro': Decimal('2.0'), 'small': Decimal('2.8'), 'medium': Decimal('3.5')},
    'jewelry-store':    {'micro': Decimal('2.3'), 'small': Decimal('3.2'), 'medium': Decimal('4.2')},
    'marketplace':      {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'print-on-demand':  {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'retail':           {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'subscription':     {'micro': Decimal('3.8'), 'small': Decimal('5.5'), 'medium': Decimal('7.0')},
    'toy-store':        {'micro': Decimal('2.0'), 'small': Decimal('2.8'), 'medium': Decimal('3.5')},

    # AUTOMOTIVE — Brookz automotive baseline 3.8x
    'auto-parts':       {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'automotive':       {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'body-shop':        {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'car-detailing':    {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'car-rental':       {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'oil-change':       {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('3.8')},
    'tire-shop':        {'micro': Decimal('2.3'), 'small': Decimal('3.2'), 'medium': Decimal('4.0')},

    # CREATIVE & MEDIA — Brookz creative/media avg 4.5x
    'advertising-agency': {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'animation':        {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'content-creation': {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'design':           {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'marketing':        {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'music-production': {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'photography':      {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'printing':         {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'social-media':     {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'videography':      {'micro': Decimal('2.3'), 'small': Decimal('3.2'), 'medium': Decimal('4.2')},

    # EDUCATION & TRAINING
    'art-classes':      {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'childcare':        {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'coaching':         {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'dance-studio':     {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'education':        {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'language-school':  {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'music-school':     {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'tutoring':         {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},

    # EVENTS & ENTERTAINMENT — Brookz events avg 3.5x
    'amusement':        {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'entertainment':    {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'events':           {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'florist':          {'micro': Decimal('2.0'), 'small': Decimal('2.8'), 'medium': Decimal('3.5')},
    'magician':         {'micro': Decimal('1.5'), 'small': Decimal('2.0'), 'medium': Decimal('2.8')},
    'party-rental':     {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'theater':          {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'venue':            {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},

    # FINANCIAL SERVICES — BDO Belgium avg 6.0x
    'credit-repair':    {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'financial-planning': {'micro': Decimal('4.2'), 'small': Decimal('6.0'), 'medium': Decimal('7.5')},
    'insurance-broker': {'micro': Decimal('4.5'), 'small': Decimal('6.5'), 'medium': Decimal('8.0')},
    'investment-advisory': {'micro': Decimal('4.2'), 'small': Decimal('6.0'), 'medium': Decimal('7.5')},
    'mortgage-broker':  {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'tax-preparation':  {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},

    # HOSPITALITY & TOURISM — Brookz/Vlerick avg 4.5x
    'bed-breakfast':    {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'campground':       {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'hotel':            {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'tour-operator':    {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'travel-agency':    {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'vacation-rental':  {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},

    # TRANSPORTATION & LOGISTICS — Vlerick avg 4.5x
    'freight-broker':   {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'limo-service':     {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'logistics':        {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'moving-company':   {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'parking-services': {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'taxi-rideshare':   {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'truck-rental':     {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'warehousing':      {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},

    # PET SERVICES
    'dog-walking':      {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'pet-grooming':     {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'pet-sitting':      {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'pet-store':        {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'pet-training':     {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'veterinary':       {'micro': Decimal('4.2'), 'small': Decimal('6.0'), 'medium': Decimal('7.5')},

    # AGRICULTURE
    'aquaculture':      {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'farm':             {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'livestock':        {'micro': Decimal('2.0'), 'small': Decimal('2.8'), 'medium': Decimal('3.5')},
    'nursery':          {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},
    'organic-farm':     {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},

    # ARTS & CRAFTS
    'art-gallery':      {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.5')},
    'crafts':           {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'jewelry-making':   {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'pottery':          {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'woodworking':      {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},

    # REPAIR & MAINTENANCE
    'appliance-repair': {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'electronics-repair': {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'furniture-repair': {'micro': Decimal('2.0'), 'small': Decimal('2.8'), 'medium': Decimal('3.5')},
    'handyman':         {'micro': Decimal('1.8'), 'small': Decimal('2.5'), 'medium': Decimal('3.2')},
    'locksmith':        {'micro': Decimal('2.5'), 'small': Decimal('3.5'), 'medium': Decimal('4.5')},

    # ENVIRONMENTAL
    'environmental-consulting': {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'pest-control':     {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'recycling':        {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'waste-management': {'micro': Decimal('3.8'), 'small': Decimal('5.5'), 'medium': Decimal('7.0')},

    # SECURITY & SAFETY
    'fire-protection':  {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'private-security': {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'safety-training':  {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'security-systems': {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},

    # MISCELLANEOUS
    'convenience-store': {'micro': Decimal('2.2'), 'small': Decimal('3.0'), 'medium': Decimal('4.0')},
    'property-management': {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'engineering':      {'micro': Decimal('3.8'), 'small': Decimal('5.5'), 'medium': Decimal('7.0')},
    'architecture':     {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
    'recruiting':       {'micro': Decimal('3.5'), 'small': Decimal('5.0'), 'medium': Decimal('6.5')},
    'training':         {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'pr':               {'micro': Decimal('2.8'), 'small': Decimal('4.0'), 'medium': Decimal('5.2')},
    'advertising':      {'micro': Decimal('3.2'), 'small': Decimal('4.5'), 'medium': Decimal('5.8')},
}
# fmt: on

# Legacy 21-category mapping (backward compatibility)
BELGIAN_SME_MULTIPLES = {
    "technology": {"micro": Decimal("4.5"), "small": Decimal("5.5"), "medium": Decimal("7.0")},
    "services": {"micro": Decimal("4.0"), "small": Decimal("5.0"), "medium": Decimal("6.0")},
    "consulting": {"micro": Decimal("4.0"), "small": Decimal("5.5"), "medium": Decimal("6.5")},
    "manufacturing": {"micro": Decimal("3.5"), "small": Decimal("4.5"), "medium": Decimal("5.5")},
    "retail": {"micro": Decimal("3.0"), "small": Decimal("4.0"), "medium": Decimal("5.0")},
    "healthcare": {"micro": Decimal("4.5"), "small": Decimal("6.0"), "medium": Decimal("7.5")},
    "food-beverage": {"micro": Decimal("2.8"), "small": Decimal("3.5"), "medium": Decimal("4.5")},
    "beauty-wellness": {"micro": Decimal("3.2"), "small": Decimal("4.0"), "medium": Decimal("5.0")},
    "home-property": {"micro": Decimal("3.5"), "small": Decimal("4.5"), "medium": Decimal("5.5")},
    "hospitality-tourism": {
        "micro": Decimal("3.0"),
        "small": Decimal("4.0"),
        "medium": Decimal("5.5"),
    },
    "creative-media": {"micro": Decimal("3.5"), "small": Decimal("4.5"), "medium": Decimal("5.5")},
    "education-training": {
        "micro": Decimal("3.5"),
        "small": Decimal("4.5"),
        "medium": Decimal("5.5"),
    },
    "events-entertainment": {
        "micro": Decimal("2.5"),
        "small": Decimal("3.5"),
        "medium": Decimal("4.5"),
    },
    "financial-services": {
        "micro": Decimal("4.5"),
        "small": Decimal("6.0"),
        "medium": Decimal("7.5"),
    },
    "fitness-health": {"micro": Decimal("3.5"), "small": Decimal("4.5"), "medium": Decimal("5.5")},
    "pet-services": {"micro": Decimal("3.0"), "small": Decimal("4.0"), "medium": Decimal("5.0")},
    "automotive": {"micro": Decimal("3.0"), "small": Decimal("4.0"), "medium": Decimal("5.0")},
    "transportation-logistics": {
        "micro": Decimal("3.0"),
        "small": Decimal("4.0"),
        "medium": Decimal("5.5"),
    },
    "agriculture": {"micro": Decimal("2.5"), "small": Decimal("3.5"), "medium": Decimal("4.5")},
    "arts-crafts": {"micro": Decimal("2.5"), "small": Decimal("3.5"), "medium": Decimal("4.5")},
    "repair-maintenance": {
        "micro": Decimal("3.0"),
        "small": Decimal("4.0"),
        "medium": Decimal("5.0"),
    },
    "environmental": {"micro": Decimal("3.5"), "small": Decimal("4.5"), "medium": Decimal("6.0")},
    "security-safety": {"micro": Decimal("3.5"), "small": Decimal("4.5"), "medium": Decimal("5.5")},
    "ecommerce-retail": {
        "micro": Decimal("3.0"),
        "small": Decimal("4.0"),
        "medium": Decimal("5.0"),
    },
}

# Benelux regional adjustment factors (Vlerick M&A Monitor deal data)
BENELUX_REGIONAL_ADJUSTMENTS = {
    "flanders": Decimal("1.05"),
    "wallonia": Decimal("0.92"),
    "brussels": Decimal("1.10"),
    "netherlands": Decimal("1.08"),
    "luxembourg": Decimal("1.12"),
}

# SME Transaction Database Multiples — 21 categories
# Pepperdine Private Capital Markets Report 2024, BizBuySell 2024.
# Based on 2,500+ closed transactions (2023-2024).
# Pepperdine baselines: micro 3.2x, small 4.3x, medium 5.5x (cross-industry).
# Industry premiums/discounts applied per Pepperdine sector analysis.
TRANSACTION_SME_MULTIPLES = {
    "technology": {
        "micro": Decimal("4.0"),
        "small": Decimal("5.0"),
        "medium": Decimal("6.5"),
    },
    "services": {
        "micro": Decimal("3.5"),
        "small": Decimal("4.5"),
        "medium": Decimal("5.5"),
    },
    "consulting": {
        "micro": Decimal("3.5"),
        "small": Decimal("4.8"),
        "medium": Decimal("5.8"),
    },
    "manufacturing": {
        "micro": Decimal("3.0"),
        "small": Decimal("4.0"),
        "medium": Decimal("5.0"),
    },
    "retail": {
        "micro": Decimal("2.5"),
        "small": Decimal("3.5"),
        "medium": Decimal("4.5"),
    },
    "healthcare": {
        "micro": Decimal("4.0"),
        "small": Decimal("5.0"),
        "medium": Decimal("6.0"),
    },
    "food-beverage": {
        "micro": Decimal("2.5"),
        "small": Decimal("3.2"),
        "medium": Decimal("4.0"),
    },
    "beauty-wellness": {
        "micro": Decimal("3.0"),
        "small": Decimal("3.8"),
        "medium": Decimal("4.8"),
    },
    "home-property": {
        "micro": Decimal("3.2"),
        "small": Decimal("4.2"),
        "medium": Decimal("5.2"),
    },
    "hospitality-tourism": {
        "micro": Decimal("2.8"),
        "small": Decimal("3.5"),
        "medium": Decimal("5.0"),
    },
    "creative-media": {
        "micro": Decimal("3.2"),
        "small": Decimal("4.2"),
        "medium": Decimal("5.2"),
    },
    "education-training": {
        "micro": Decimal("3.2"),
        "small": Decimal("4.2"),
        "medium": Decimal("5.2"),
    },
    "events-entertainment": {
        "micro": Decimal("2.2"),
        "small": Decimal("3.2"),
        "medium": Decimal("4.2"),
    },
    "financial-services": {
        "micro": Decimal("4.0"),
        "small": Decimal("5.5"),
        "medium": Decimal("7.0"),
    },
    "fitness-health": {
        "micro": Decimal("3.2"),
        "small": Decimal("4.2"),
        "medium": Decimal("5.2"),
    },
    "pet-services": {
        "micro": Decimal("2.8"),
        "small": Decimal("3.5"),
        "medium": Decimal("4.5"),
    },
    "automotive": {
        "micro": Decimal("2.8"),
        "small": Decimal("3.5"),
        "medium": Decimal("4.5"),
    },
    "transportation-logistics": {
        "micro": Decimal("2.8"),
        "small": Decimal("3.5"),
        "medium": Decimal("5.0"),
    },
    "agriculture": {
        "micro": Decimal("2.2"),
        "small": Decimal("3.2"),
        "medium": Decimal("4.2"),
    },
    "arts-crafts": {
        "micro": Decimal("2.2"),
        "small": Decimal("3.2"),
        "medium": Decimal("4.2"),
    },
    "repair-maintenance": {
        "micro": Decimal("2.8"),
        "small": Decimal("3.5"),
        "medium": Decimal("4.5"),
    },
    "environmental": {
        "micro": Decimal("3.2"),
        "small": Decimal("4.2"),
        "medium": Decimal("5.5"),
    },
    "security-safety": {
        "micro": Decimal("3.2"),
        "small": Decimal("4.2"),
        "medium": Decimal("5.2"),
    },
    "ecommerce-retail": {
        "micro": Decimal("2.5"),
        "small": Decimal("3.5"),
        "medium": Decimal("4.5"),
    },
}

# Revenue Multiples for SMEs — 21 categories (Trugman 2017, West 2012,
# BizBuySell 2024 sector medians, BDO Belgium M&A Monitor 2024)
SME_REVENUE_MULTIPLES = {
    "technology": {
        "micro": Decimal("1.2"),
        "small": Decimal("1.5"),
        "medium": Decimal("2.0"),
    },
    "services": {
        "micro": Decimal("0.8"),
        "small": Decimal("1.0"),
        "medium": Decimal("1.2"),
    },
    "consulting": {
        "micro": Decimal("1.0"),
        "small": Decimal("1.2"),
        "medium": Decimal("1.5"),
    },
    "manufacturing": {
        "micro": Decimal("0.5"),
        "small": Decimal("0.7"),
        "medium": Decimal("0.9"),
    },
    "retail": {
        "micro": Decimal("0.3"),
        "small": Decimal("0.4"),
        "medium": Decimal("0.6"),
    },
    "healthcare": {
        "micro": Decimal("1.0"),
        "small": Decimal("1.3"),
        "medium": Decimal("1.8"),
    },
    "food-beverage": {
        "micro": Decimal("0.4"),
        "small": Decimal("0.6"),
        "medium": Decimal("0.8"),
    },
    "beauty-wellness": {
        "micro": Decimal("0.7"),
        "small": Decimal("0.9"),
        "medium": Decimal("1.1"),
    },
    "home-property": {
        "micro": Decimal("0.5"),
        "small": Decimal("0.7"),
        "medium": Decimal("0.9"),
    },
    "hospitality-tourism": {
        "micro": Decimal("0.6"),
        "small": Decimal("0.8"),
        "medium": Decimal("1.2"),
    },
    "creative-media": {
        "micro": Decimal("0.8"),
        "small": Decimal("1.0"),
        "medium": Decimal("1.3"),
    },
    "education-training": {
        "micro": Decimal("0.7"),
        "small": Decimal("0.9"),
        "medium": Decimal("1.1"),
    },
    "events-entertainment": {
        "micro": Decimal("0.4"),
        "small": Decimal("0.6"),
        "medium": Decimal("0.8"),
    },
    "financial-services": {
        "micro": Decimal("1.2"),
        "small": Decimal("1.5"),
        "medium": Decimal("2.0"),
    },
    "fitness-health": {
        "micro": Decimal("0.7"),
        "small": Decimal("0.9"),
        "medium": Decimal("1.2"),
    },
    "pet-services": {
        "micro": Decimal("0.5"),
        "small": Decimal("0.7"),
        "medium": Decimal("0.9"),
    },
    "automotive": {
        "micro": Decimal("0.4"),
        "small": Decimal("0.6"),
        "medium": Decimal("0.8"),
    },
    "transportation-logistics": {
        "micro": Decimal("0.4"),
        "small": Decimal("0.6"),
        "medium": Decimal("0.9"),
    },
    "agriculture": {
        "micro": Decimal("0.3"),
        "small": Decimal("0.5"),
        "medium": Decimal("0.7"),
    },
    "arts-crafts": {
        "micro": Decimal("0.4"),
        "small": Decimal("0.5"),
        "medium": Decimal("0.7"),
    },
    "repair-maintenance": {
        "micro": Decimal("0.5"),
        "small": Decimal("0.6"),
        "medium": Decimal("0.8"),
    },
    "environmental": {
        "micro": Decimal("0.7"),
        "small": Decimal("0.9"),
        "medium": Decimal("1.2"),
    },
    "security-safety": {
        "micro": Decimal("0.7"),
        "small": Decimal("0.9"),
        "medium": Decimal("1.1"),
    },
    "ecommerce-retail": {
        "micro": Decimal("0.3"),
        "small": Decimal("0.5"),
        "medium": Decimal("0.7"),
    },
}
