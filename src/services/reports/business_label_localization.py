"""Business-type label normalization for report display."""

from src.services.infrastructure.translations import normalize_report_locale

# English: canonical display forms and synonym normalization (e.g. "dining" -> "Restaurant")
BUSINESS_TYPE_TRANSLATIONS_EN = {
    # Food & Beverage / Hospitality
    "dining": "Restaurant",
    "casual dining": "Restaurant",
    "horeca": "Restaurant",
    "food & beverage": "Restaurant",
    "food & beverages": "Restaurant",
    "food-beverage": "Restaurant",
    "food-beverages": "Restaurant",
    "food beverage": "Restaurant",
    "food beverages": "Restaurant",
    "restaurant": "Restaurant",
    "restaurants": "Restaurant",
    "cafe": "Café",
    "café": "Café",
    "bistro": "Restaurant",
    "eatery": "Restaurant",
    "food service": "Restaurant",
    "bakery": "Bakery",
    "bakkerij": "Bakery",
    "baker": "Bakery",
    "baked-goods": "Bakery",
    "baked goods": "Bakery",
    "catering": "Catering",
    "coffee shop": "Coffee Shop",
    "coffee-shop": "Coffee Shop",
    # Retail & Commerce
    "retail": "Retail",
    "store": "Retail Store",
    "shop": "Retail Store",
    "ecommerce": "E-commerce",
    "e-commerce": "E-commerce",
    "online store": "E-commerce",
    # Professional Services
    "services": "Services",
    "consulting": "Business Consulting",
    "consultancy": "Business Consulting",
    "accounting": "Accounting & Finance",
    "legal": "Legal Services",
    "healthcare": "Healthcare Services",
    "medical": "Healthcare Services",
    # Tech
    "saas": "SaaS",
    "software": "Software Development",
    "technology": "Technology",
    "tech": "Technology",
    # Other
    "manufacturing": "Manufacturing",
    "logistics": "Logistics & Delivery",
    "transport": "Transport",
    "education": "Education & Training",
    "real estate": "Real Estate",
    "realestate": "Real Estate",
    "finance": "Finance",
    "construction": "Construction",
    "energy": "Energy",
    "creative": "Creative",
    "agriculture": "Agriculture",
    "home-services": "Home Services",
    "home services": "Home Services",
    "food-production": "Food Production",
    "food production": "Food Production",
    # Category IDs (from synced_business_categories)
    "food-beverage": "Restaurant",
    "beauty-wellness": "Beauty & Wellness",
    "fitness-health": "Fitness & Health",
    "creative-media": "Creative & Media",
    "tech-digital": "Tech & Digital",
    "ecommerce-retail": "E-commerce & Retail",
    "home-property": "Home & Property",
    "professional-services": "Professional Services",
    "education-training": "Education & Training",
    "transportation-logistics": "Transportation & Logistics",
    "events-entertainment": "Events & Entertainment",
    "financial-services": "Financial Services",
    "pet-services": "Pet Services",
    "automotive": "Automotive Services",
    "auto-parts": "Auto Parts",
    "auto parts": "Auto Parts",
    "hospitality-tourism": "Hospitality & Tourism",
    "agriculture": "Agriculture & Farming",
    "arts-crafts": "Arts & Crafts",
    "repair-maintenance": "Repair & Maintenance",
    "security-safety": "Security & Safety",
    "environmental": "Environmental Services",
    "party-rental": "Party Rental",
    "party rental": "Party Rental",
    "partyverhuur": "Party Rental",
}

# Dutch (Belgian/Flemish): professional business terminology
BUSINESS_TYPE_TRANSLATIONS_NL = {
    # Food & Beverage / Horeca
    "dining": "Restaurant",
    "casual dining": "Restaurant",
    "horeca": "Restaurant",
    "food & beverage": "Restaurant",
    "food & beverages": "Restaurant",
    "food-beverage": "Restaurant",
    "food-beverages": "Restaurant",
    "food beverage": "Restaurant",
    "food beverages": "Restaurant",
    "restaurant": "Restaurant",
    "restaurants": "Restaurant",
    "cafe": "Café",
    "café": "Café",
    "bistro": "Restaurant",
    "eatery": "Restaurant",
    "food service": "Restaurant",
    "bakery": "Bakkerij",
    "bakkerij": "Bakkerij",
    "baker": "Bakker",
    "baked-goods": "Bakkerij",
    "baked goods": "Bakkerij",
    "catering": "Catering",
    "coffee shop": "Koffiebar",
    "coffee-shop": "Koffiebar",
    # Retail & Commerce
    "retail": "Detailhandel",
    "store": "Winkel",
    "shop": "Winkel",
    "ecommerce": "E-commerce",
    "e-commerce": "E-commerce",
    "online store": "Webwinkel",
    # Professional Services
    "services": "Diensten",
    "consulting": "Adviesbureau",
    "consultancy": "Adviesbureau",
    "accounting": "Boekhouding & Financiën",
    "legal": "Juridische Diensten",
    "healthcare": "Gezondheidszorg",
    "medical": "Medisch",
    # Tech
    "saas": "SaaS",
    "software": "Softwareontwikkeling",
    "technology": "Technologie",
    "tech": "Technologie",
    # Other
    "manufacturing": "Productie",
    "logistics": "Logistiek",
    "transport": "Transport",
    "education": "Onderwijs",
    "real estate": "Vastgoed",
    "realestate": "Vastgoed",
    "finance": "Financiën",
    "construction": "Bouw",
    "energy": "Energie",
    "creative": "Creatief",
    "agriculture": "Landbouw",
    "home-services": "Bouw",
    "home services": "Bouw",
    "food-production": "Voedingsproductie",
    "food production": "Voedingsproductie",
    # Category IDs (from synced_business_categories) - Flemish/Belgian terminology
    "food-beverage": "Horeca",
    "beauty-wellness": "Schoonheid & Wellness",
    "fitness-health": "Fitness & Gezondheid",
    "creative-media": "Creatief & Media",
    "tech-digital": "Technologie & Digitaal",
    "ecommerce-retail": "E-commerce & Detailhandel",
    "home-property": "Woning & Vastgoed",
    "professional-services": "Professionele Diensten",
    "education-training": "Onderwijs & Opleiding",
    "transportation-logistics": "Transport & Logistiek",
    "events-entertainment": "Evenementen & Entertainment",
    "financial-services": "Financiële Diensten",
    "pet-services": "Dierverzorging",
    "automotive": "Automobiel",
    "auto-parts": "Auto-onderdelen",
    "auto parts": "Auto-onderdelen",
    "hospitality-tourism": "Toerisme & Gastvrijheid",
    "arts-crafts": "Kunst & Ambacht",
    "repair-maintenance": "Reparatie & Onderhoud",
    "security-safety": "Beveiliging & Veiligheid",
    "environmental": "Milieudiensten",
    "party-rental": "Partyverhuur",
    "party rental": "Partyverhuur",
    "partyverhuur": "Partyverhuur",
}


def localize_business_label(label: str | None, locale: str = "nl") -> str | None:
    """Localize and normalize business type labels for report display.

    VAL-2026-35A4 (2026-05-27) — robust EN→NL reverse lookup:
    callers sometimes hand us a label that has already been translated to the
    EN canonical form (e.g. "Accounting & Finance" from a pre-formatted
    benchmark contract). The base map only keyed the NACE-shape inputs
    ("accounting" → "Boekhouding & Financiën"), so an EN canonical form
    leaked through unchanged on Dutch reports — the Creatief bureau cover
    badge read "Accounting & Finance" inside an otherwise NL report.

    Resolution order:
      1) Direct lookup in the target-locale map (original behaviour).
      2) When the target is NL and step 1 missed, walk the EN map for a
         value equal to the input and substitute the matching NL value at
         the same key.
      3) When the target is EN and step 1 missed, mirror the same trick
         using the NL map as the source.
      4) Fallthrough — return the input unchanged.
    """
    if not label:
        return label

    normalized = str(label).strip()
    if not normalized:
        return label

    key = normalized.lower()
    target_en = normalize_report_locale(locale) == "en"
    if target_en:
        translated = BUSINESS_TYPE_TRANSLATIONS_EN.get(key)
    else:
        translated = BUSINESS_TYPE_TRANSLATIONS_NL.get(key)

    if translated:
        return translated

    # Reverse lookup: the input is already a canonical form in the OTHER
    # locale; find the source key and translate to the target locale.
    if target_en:
        for k, nl_value in BUSINESS_TYPE_TRANSLATIONS_NL.items():
            if nl_value.lower() == key:
                en_value = BUSINESS_TYPE_TRANSLATIONS_EN.get(k)
                if en_value:
                    return en_value
    else:
        for k, en_value in BUSINESS_TYPE_TRANSLATIONS_EN.items():
            if en_value.lower() == key:
                nl_value = BUSINESS_TYPE_TRANSLATIONS_NL.get(k)
                if nl_value:
                    return nl_value

    return normalized
