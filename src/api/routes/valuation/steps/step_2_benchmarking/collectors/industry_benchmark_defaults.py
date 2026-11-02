"""Static fallback multiples used by the Step 2 benchmark collector."""

from decimal import Decimal

# Business type defaults — all active types from synced_business_types.json.
# Kept as last-resort fallback; secondary to DB-driven multiples.
# Values aligned with fallback_multiples.py (BizBuySell + Belgian calibration).
# Sources: VFB Belgium 2024, BDO Belgium M&A Monitor 2024, Pepperdine 2024.
BUSINESS_TYPE_DEFAULTS = {
    # ── FOOD & BEVERAGE ───────────────────────────────────────────
    "restaurant": {"ev_ebitda": Decimal("3.2"), "ev_revenue": Decimal("0.85"), "pe": Decimal("12")},
    "bakery": {"ev_ebitda": Decimal("2.8"), "ev_revenue": Decimal("0.7"), "pe": Decimal("12")},
    "coffee-shop": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
    "bar-pub": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
    "catering": {"ev_ebitda": Decimal("3.0"), "ev_revenue": Decimal("0.8"), "pe": Decimal("11")},
    "food-truck": {"ev_ebitda": Decimal("2.5"), "ev_revenue": Decimal("0.6"), "pe": Decimal("10")},
    "brewery": {"ev_ebitda": Decimal("4.5"), "ev_revenue": Decimal("1.2"), "pe": Decimal("14")},
    "chef": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.1"), "pe": Decimal("13")},
    "meals": {"ev_ebitda": Decimal("3.2"), "ev_revenue": Decimal("0.8"), "pe": Decimal("12")},
    "grocery-specialty": {
        "ev_ebitda": Decimal("3.0"),
        "ev_revenue": Decimal("0.7"),
        "pe": Decimal("11"),
    },
    "butcher": {"ev_ebitda": Decimal("3.2"), "ev_revenue": Decimal("0.8"), "pe": Decimal("12")},
    "food-distribution": {
        "ev_ebitda": Decimal("2.8"),
        "ev_revenue": Decimal("0.6"),
        "pe": Decimal("10"),
    },
    "fruit-vegetable": {
        "ev_ebitda": Decimal("2.5"),
        "ev_revenue": Decimal("0.6"),
        "pe": Decimal("10"),
    },
    "convenience-store": {
        "ev_ebitda": Decimal("3.3"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    "ice-cream": {"ev_ebitda": Decimal("2.8"), "ev_revenue": Decimal("0.7"), "pe": Decimal("11")},
    "juice-bar": {"ev_ebitda": Decimal("2.8"), "ev_revenue": Decimal("0.7"), "pe": Decimal("11")},
    "winery": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.0"), "pe": Decimal("13")},
    # ── BEAUTY & WELLNESS ─────────────────────────────────────────
    "hairstyling": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.1"), "pe": Decimal("13")},
    "nail-salon": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "spa": {"ev_ebitda": Decimal("4.2"), "ev_revenue": Decimal("1.3"), "pe": Decimal("14")},
    "massage": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "skincare-clinic": {
        "ev_ebitda": Decimal("4.6"),
        "ev_revenue": Decimal("1.4"),
        "pe": Decimal("14"),
    },
    "tattoo-parlor": {
        "ev_ebitda": Decimal("3.8"),
        "ev_revenue": Decimal("1.1"),
        "pe": Decimal("13"),
    },
    "piercing-studio": {
        "ev_ebitda": Decimal("3.5"),
        "ev_revenue": Decimal("1.0"),
        "pe": Decimal("12"),
    },
    "wellness": {"ev_ebitda": Decimal("4.2"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "barber-shop": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "beauty-supply": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    "makeup": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "tanning-salon": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    # NACE 96.09 residual. Owner-operated and unspecified by construction, so it
    # takes the conservative end of the personal-service peer set.
    "personal-services": {
        "ev_ebitda": Decimal("3.4"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    # ── FITNESS & HEALTH ──────────────────────────────────────────
    "fitness-studio": {
        "ev_ebitda": Decimal("4.5"),
        "ev_revenue": Decimal("1.4"),
        "pe": Decimal("13"),
    },
    "yoga-studio": {"ev_ebitda": Decimal("4.2"), "ev_revenue": Decimal("1.3"), "pe": Decimal("13")},
    "dance-studio": {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("13"),
    },
    "gym": {"ev_ebitda": Decimal("4.8"), "ev_revenue": Decimal("1.5"), "pe": Decimal("14")},
    "chiropractic": {
        "ev_ebitda": Decimal("4.7"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    "physical-therapy": {
        "ev_ebitda": Decimal("4.9"),
        "ev_revenue": Decimal("1.6"),
        "pe": Decimal("14"),
    },
    "mental-health": {
        "ev_ebitda": Decimal("5.1"),
        "ev_revenue": Decimal("1.7"),
        "pe": Decimal("15"),
    },
    "healthcare": {"ev_ebitda": Decimal("5.0"), "ev_revenue": Decimal("1.5"), "pe": Decimal("14")},
    "personaltraining": {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("13"),
    },
    "martial-arts": {
        "ev_ebitda": Decimal("3.8"),
        "ev_revenue": Decimal("1.1"),
        "pe": Decimal("13"),
    },
    "nutrition-counseling": {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("13"),
    },
    "pilates-studio": {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("13"),
    },
    # ── HOME & PROPERTY ───────────────────────────────────────────
    "cleaning": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.2"), "pe": Decimal("12")},
    "landscaping": {"ev_ebitda": Decimal("4.5"), "ev_revenue": Decimal("1.5"), "pe": Decimal("13")},
    "plumbing": {"ev_ebitda": Decimal("4.2"), "ev_revenue": Decimal("1.3"), "pe": Decimal("13")},
    "electrical": {"ev_ebitda": Decimal("4.3"), "ev_revenue": Decimal("1.4"), "pe": Decimal("13")},
    "hvac": {"ev_ebitda": Decimal("4.8"), "ev_revenue": Decimal("1.6"), "pe": Decimal("14")},
    "construction": {
        "ev_ebitda": Decimal("3.5"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("11"),
    },
    "interior-design": {
        "ev_ebitda": Decimal("4.9"),
        "ev_revenue": Decimal("1.6"),
        "pe": Decimal("14"),
    },
    "realestate": {"ev_ebitda": Decimal("5.5"), "ev_revenue": Decimal("1.8"), "pe": Decimal("15")},
    "roofing": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "painting": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    # ── PET SERVICES ──────────────────────────────────────────────
    "pet-grooming": {
        "ev_ebitda": Decimal("3.8"),
        "ev_revenue": Decimal("1.1"),
        "pe": Decimal("13"),
    },
    "pet-sitting": {"ev_ebitda": Decimal("3.6"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "pet-store": {"ev_ebitda": Decimal("3.3"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
    "pet-training": {
        "ev_ebitda": Decimal("4.1"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("13"),
    },
    "veterinary": {"ev_ebitda": Decimal("5.0"), "ev_revenue": Decimal("1.7"), "pe": Decimal("14")},
    "dog-walking": {"ev_ebitda": Decimal("3.0"), "ev_revenue": Decimal("0.8"), "pe": Decimal("11")},
    # ── AUTOMOTIVE ────────────────────────────────────────────────
    "oil-change": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.1"), "pe": Decimal("13")},
    "tire-shop": {"ev_ebitda": Decimal("3.6"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "body-shop": {"ev_ebitda": Decimal("4.1"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "car-detailing": {
        "ev_ebitda": Decimal("3.5"),
        "ev_revenue": Decimal("1.0"),
        "pe": Decimal("12"),
    },
    "automotive": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("0.8"), "pe": Decimal("12")},
    "auto-parts": {"ev_ebitda": Decimal("3.0"), "ev_revenue": Decimal("0.7"), "pe": Decimal("11")},
    "car-rental": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
    # ── PROFESSIONAL SERVICES ─────────────────────────────────────
    "accounting": {"ev_ebitda": Decimal("5.2"), "ev_revenue": Decimal("1.8"), "pe": Decimal("15")},
    "bookkeeping": {"ev_ebitda": Decimal("4.8"), "ev_revenue": Decimal("1.5"), "pe": Decimal("14")},
    "legal": {"ev_ebitda": Decimal("4.9"), "ev_revenue": Decimal("1.6"), "pe": Decimal("14")},
    "consulting": {"ev_ebitda": Decimal("5.8"), "ev_revenue": Decimal("2.0"), "pe": Decimal("15")},
    "business-support": {
        "ev_ebitda": Decimal("5"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("12.5"),
    },
    "marketing": {"ev_ebitda": Decimal("4.6"), "ev_revenue": Decimal("1.5"), "pe": Decimal("14")},
    "recruiting": {"ev_ebitda": Decimal("5.3"), "ev_revenue": Decimal("1.8"), "pe": Decimal("15")},
    "coaching": {"ev_ebitda": Decimal("4.3"), "ev_revenue": Decimal("1.3"), "pe": Decimal("13")},
    "engineering": {"ev_ebitda": Decimal("5.1"), "ev_revenue": Decimal("1.7"), "pe": Decimal("15")},
    "architecture": {
        "ev_ebitda": Decimal("5.6"),
        "ev_revenue": Decimal("1.9"),
        "pe": Decimal("15"),
    },
    "business-brokerage": {
        "ev_ebitda": Decimal("5.2"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("15"),
    },
    "hr": {"ev_ebitda": Decimal("4.8"), "ev_revenue": Decimal("1.5"), "pe": Decimal("14")},
    "notary": {"ev_ebitda": Decimal("5.0"), "ev_revenue": Decimal("1.8"), "pe": Decimal("14")},
    "payroll": {"ev_ebitda": Decimal("5.0"), "ev_revenue": Decimal("1.6"), "pe": Decimal("14")},
    "translation": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "virtual-assistant": {
        "ev_ebitda": Decimal("3.5"),
        "ev_revenue": Decimal("1.0"),
        "pe": Decimal("12"),
    },
    "market-research": {
        "ev_ebitda": Decimal("5.0"),
        "ev_revenue": Decimal("1.6"),
        "pe": Decimal("14"),
    },
    "public-relations": {
        "ev_ebitda": Decimal("4.7"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    "tax-preparation": {
        "ev_ebitda": Decimal("5.0"),
        "ev_revenue": Decimal("1.6"),
        "pe": Decimal("14"),
    },
    "general-business": {
        "ev_ebitda": Decimal("5"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("12.5"),
    },
    # ── TECH & DIGITAL ────────────────────────────────────────────
    "itsupport": {"ev_ebitda": Decimal("4.5"), "ev_revenue": Decimal("1.4"), "pe": Decimal("14")},
    "computer-repair": {
        "ev_ebitda": Decimal("3.9"),
        "ev_revenue": Decimal("1.1"),
        "pe": Decimal("13"),
    },
    "saas": {"ev_ebitda": Decimal("6.5"), "ev_revenue": Decimal("2.5"), "pe": Decimal("16")},
    "software": {"ev_ebitda": Decimal("6.0"), "ev_revenue": Decimal("2.2"), "pe": Decimal("16")},
    "webdev": {"ev_ebitda": Decimal("4.5"), "ev_revenue": Decimal("1.4"), "pe": Decimal("14")},
    "ai-ml": {"ev_ebitda": Decimal("6.0"), "ev_revenue": Decimal("2.0"), "pe": Decimal("16")},
    "blockchain": {"ev_ebitda": Decimal("5.5"), "ev_revenue": Decimal("1.8"), "pe": Decimal("15")},
    "cloud-services": {
        "ev_ebitda": Decimal("5.8"),
        "ev_revenue": Decimal("2.0"),
        "pe": Decimal("15"),
    },
    "cybersecurity": {
        "ev_ebitda": Decimal("6.2"),
        "ev_revenue": Decimal("2.2"),
        "pe": Decimal("16"),
    },
    "data-analytics": {
        "ev_ebitda": Decimal("5.5"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("15"),
    },
    "deeptech-ai-research": {
        "ev_ebitda": Decimal("6.6"),
        "ev_revenue": Decimal("2.2"),
        "pe": Decimal("18"),
    },
    "game-development": {
        "ev_ebitda": Decimal("5.0"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    "mobile-app": {"ev_ebitda": Decimal("5.5"), "ev_revenue": Decimal("1.8"), "pe": Decimal("15")},
    "seo-services": {
        "ev_ebitda": Decimal("4.5"),
        "ev_revenue": Decimal("1.4"),
        "pe": Decimal("14"),
    },
    "tech-training": {
        "ev_ebitda": Decimal("4.2"),
        "ev_revenue": Decimal("1.3"),
        "pe": Decimal("13"),
    },
    "ui-ux-design": {
        "ev_ebitda": Decimal("4.8"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    # ── HEALTHCARE (dental, optometry etc.) ───────────────────────
    "dental": {"ev_ebitda": Decimal("5.2"), "ev_revenue": Decimal("1.8"), "pe": Decimal("15")},
    "optometry": {"ev_ebitda": Decimal("5.5"), "ev_revenue": Decimal("1.9"), "pe": Decimal("15")},
    "home-health": {"ev_ebitda": Decimal("4.3"), "ev_revenue": Decimal("1.3"), "pe": Decimal("13")},
    "medical-device": {
        "ev_ebitda": Decimal("6.3"),
        "ev_revenue": Decimal("2.1"),
        "pe": Decimal("16"),
    },
    "biotech-medtech": {
        "ev_ebitda": Decimal("6"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("14"),
    },
    "biotech-pharma": {
        "ev_ebitda": Decimal("6"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("14"),
    },
    "telemedicine": {
        "ev_ebitda": Decimal("5.5"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("15"),
    },
    # Licence-bound officine: scarcity supports a multiple above dental/optometry,
    # but the ~8% EBITDA margin forces a far lower EV/Revenue than its peers
    # (EV/Revenue ~= EBITDA margin x EV/EBITDA).
    "pharmacy": {"ev_ebitda": Decimal("6.0"), "ev_revenue": Decimal("0.5"), "pe": Decimal("15")},
    # ── ECOMMERCE & RETAIL ────────────────────────────────────────
    "retail": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
    "jewelry-store": {
        "ev_ebitda": Decimal("3.5"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    "ecommerce": {"ev_ebitda": Decimal("3.2"), "ev_revenue": Decimal("0.7"), "pe": Decimal("12")},
    "subscription": {
        "ev_ebitda": Decimal("4.8"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    "affiliate-marketing": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    "bookstore": {"ev_ebitda": Decimal("2.5"), "ev_revenue": Decimal("0.5"), "pe": Decimal("10")},
    "clothing-store": {
        "ev_ebitda": Decimal("3.0"),
        "ev_revenue": Decimal("0.6"),
        "pe": Decimal("11"),
    },
    "digital-products": {
        "ev_ebitda": Decimal("4.8"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    "dropshipping": {
        "ev_ebitda": Decimal("2.5"),
        "ev_revenue": Decimal("0.4"),
        "pe": Decimal("10"),
    },
    "marketplace": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "marketplace-b2b": {
        "ev_ebitda": Decimal("5"),
        "ev_revenue": Decimal("1.6"),
        "pe": Decimal("13"),
    },
    "print-on-demand": {
        "ev_ebitda": Decimal("2.8"),
        "ev_revenue": Decimal("0.5"),
        "pe": Decimal("11"),
    },
    "toy-store": {"ev_ebitda": Decimal("2.8"), "ev_revenue": Decimal("0.6"), "pe": Decimal("11")},
    # ── MANUFACTURING ─────────────────────────────────────────────
    "manufacturing": {
        "ev_ebitda": Decimal("4.2"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    "metal-fabrication": {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    "plastics-manufacturing": {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    "general-manufacturing": {
        "ev_ebitda": Decimal("4.2"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    "manufacturing-general": {
        "ev_ebitda": Decimal("3.6"),
        "ev_revenue": Decimal("1"),
        "pe": Decimal("20.7"),
    },
    "electronics-manufacturing": {
        "ev_ebitda": Decimal("4.5"),
        "ev_revenue": Decimal("1.0"),
        "pe": Decimal("13"),
    },
    "textile-manufacturing": {
        "ev_ebitda": Decimal("3.5"),
        "ev_revenue": Decimal("0.7"),
        "pe": Decimal("11"),
    },
    "hardware-iot": {
        "ev_ebitda": Decimal("3.6"),
        "ev_revenue": Decimal("1"),
        "pe": Decimal("20.7"),
    },
    "hardware-robotics": {
        "ev_ebitda": Decimal("3.6"),
        "ev_revenue": Decimal("1"),
        "pe": Decimal("20.7"),
    },
    # ── FINANCIAL SERVICES ────────────────────────────────────────
    "financial-planning": {
        "ev_ebitda": Decimal("6.5"),
        "ev_revenue": Decimal("2.2"),
        "pe": Decimal("16"),
    },
    "insurance-broker": {
        "ev_ebitda": Decimal("6.0"),
        "ev_revenue": Decimal("2.0"),
        "pe": Decimal("16"),
    },
    "credit-repair": {
        "ev_ebitda": Decimal("4.8"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    "fintech-insurtech": {
        "ev_ebitda": Decimal("6.5"),
        "ev_revenue": Decimal("2"),
        "pe": Decimal("15"),
    },
    "fintech-lending": {
        "ev_ebitda": Decimal("6"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("14"),
    },
    "fintech-payments": {
        "ev_ebitda": Decimal("6"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("14"),
    },
    "holding-company": {
        "ev_ebitda": Decimal("6"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("14"),
    },
    "investment-advisory": {
        "ev_ebitda": Decimal("6.0"),
        "ev_revenue": Decimal("2.0"),
        "pe": Decimal("16"),
    },
    "mortgage-broker": {
        "ev_ebitda": Decimal("5.5"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("15"),
    },
    # ── HOSPITALITY & TOURISM ─────────────────────────────────────
    "hotel": {"ev_ebitda": Decimal("5.5"), "ev_revenue": Decimal("1.8"), "pe": Decimal("15")},
    "bed-breakfast": {
        "ev_ebitda": Decimal("5.2"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("15"),
    },
    "vacation-rental": {
        "ev_ebitda": Decimal("5.0"),
        "ev_revenue": Decimal("1.6"),
        "pe": Decimal("14"),
    },
    "travel-agency": {
        "ev_ebitda": Decimal("3.9"),
        "ev_revenue": Decimal("1.1"),
        "pe": Decimal("13"),
    },
    "tour-operator": {
        "ev_ebitda": Decimal("4.3"),
        "ev_revenue": Decimal("1.3"),
        "pe": Decimal("13"),
    },
    "campground": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("1.3"), "pe": Decimal("13")},
    # ── EDUCATION & TRAINING ──────────────────────────────────────
    "education": {"ev_ebitda": Decimal("4.1"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "tutoring": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.1"), "pe": Decimal("13")},
    "training": {"ev_ebitda": Decimal("4.5"), "ev_revenue": Decimal("1.4"), "pe": Decimal("14")},
    "music-school": {
        "ev_ebitda": Decimal("4.1"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("13"),
    },
    "art-classes": {"ev_ebitda": Decimal("3.2"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
    "childcare": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.0"), "pe": Decimal("13")},
    "language-school": {
        "ev_ebitda": Decimal("3.8"),
        "ev_revenue": Decimal("1.1"),
        "pe": Decimal("13"),
    },
    # ── EVENTS & ENTERTAINMENT ────────────────────────────────────
    "amusement": {"ev_ebitda": Decimal("3.0"), "ev_revenue": Decimal("0.8"), "pe": Decimal("11")},
    "entertainment": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    "events": {"ev_ebitda": Decimal("3.2"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
    "venue": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "magician": {"ev_ebitda": Decimal("2.5"), "ev_revenue": Decimal("0.7"), "pe": Decimal("10")},
    "party-rental": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    "theater": {"ev_ebitda": Decimal("3.0"), "ev_revenue": Decimal("0.8"), "pe": Decimal("11")},
    "florist": {"ev_ebitda": Decimal("2.8"), "ev_revenue": Decimal("0.8"), "pe": Decimal("11")},
    # ── TRANSPORTATION & LOGISTICS ────────────────────────────────
    "logistics": {"ev_ebitda": Decimal("4.2"), "ev_revenue": Decimal("0.9"), "pe": Decimal("13")},
    "parking-services": {
        "ev_ebitda": Decimal("4.5"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("13"),
    },
    "freight-broker": {
        "ev_ebitda": Decimal("3.5"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    "limo-service": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    "moving-company": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    "taxi-rideshare": {
        "ev_ebitda": Decimal("2.8"),
        "ev_revenue": Decimal("0.7"),
        "pe": Decimal("11"),
    },
    "truck-rental": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    "warehousing": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("1.0"), "pe": Decimal("13")},
    "wholesale-distribution": {
        "ev_ebitda": Decimal("4"),
        "ev_revenue": Decimal("0.3"),
        "pe": Decimal("11"),
    },
    # ── AGRICULTURE ───────────────────────────────────────────────
    "farm": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "nursery": {"ev_ebitda": Decimal("4.1"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "aquaculture": {"ev_ebitda": Decimal("2.8"), "ev_revenue": Decimal("0.6"), "pe": Decimal("11")},
    "livestock": {"ev_ebitda": Decimal("2.5"), "ev_revenue": Decimal("0.5"), "pe": Decimal("10")},
    "organic-farm": {
        "ev_ebitda": Decimal("3.0"),
        "ev_revenue": Decimal("0.7"),
        "pe": Decimal("11"),
    },
    # ── ARTS & CRAFTS ─────────────────────────────────────────────
    "art-gallery": {"ev_ebitda": Decimal("3.6"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "pottery": {"ev_ebitda": Decimal("3.3"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
    "crafts": {"ev_ebitda": Decimal("3.1"), "ev_revenue": Decimal("0.8"), "pe": Decimal("11")},
    "woodworking": {"ev_ebitda": Decimal("3.6"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "jewelry-making": {
        "ev_ebitda": Decimal("3.0"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("11"),
    },
    # ── REPAIR & MAINTENANCE ──────────────────────────────────────
    "handyman": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.1"), "pe": Decimal("13")},
    "locksmith": {"ev_ebitda": Decimal("3.5"), "ev_revenue": Decimal("1.0"), "pe": Decimal("12")},
    "pest-control": {
        "ev_ebitda": Decimal("4.5"),
        "ev_revenue": Decimal("1.4"),
        "pe": Decimal("14"),
    },
    "appliance-repair": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    "electronics-repair": {
        "ev_ebitda": Decimal("3.2"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    "furniture-repair": {
        "ev_ebitda": Decimal("3.0"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("11"),
    },
    # ── ENVIRONMENTAL ─────────────────────────────────────────────
    "waste-management": {
        "ev_ebitda": Decimal("4.7"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    "environmental-consulting": {
        "ev_ebitda": Decimal("4.5"),
        "ev_revenue": Decimal("1.4"),
        "pe": Decimal("14"),
    },
    "recycling": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("1.0"), "pe": Decimal("13")},
    "utilities": {"ev_ebitda": Decimal("5.5"), "ev_revenue": Decimal("0.55"), "pe": Decimal("13")},
    # ── SECURITY & SAFETY ─────────────────────────────────────────
    "fire-protection": {
        "ev_ebitda": Decimal("4.2"),
        "ev_revenue": Decimal("1.3"),
        "pe": Decimal("13"),
    },
    "private-security": {
        "ev_ebitda": Decimal("4.2"),
        "ev_revenue": Decimal("1.3"),
        "pe": Decimal("13"),
    },
    "safety-training": {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("13"),
    },
    "security-systems": {
        "ev_ebitda": Decimal("4.5"),
        "ev_revenue": Decimal("1.4"),
        "pe": Decimal("14"),
    },
    # ── CREATIVE MEDIA ────────────────────────────────────────────
    "design": {"ev_ebitda": Decimal("4.4"), "ev_revenue": Decimal("1.4"), "pe": Decimal("14")},
    "photography": {"ev_ebitda": Decimal("4.2"), "ev_revenue": Decimal("1.3"), "pe": Decimal("13")},
    "advertising": {"ev_ebitda": Decimal("4.9"), "ev_revenue": Decimal("1.6"), "pe": Decimal("14")},
    "pr": {"ev_ebitda": Decimal("4.7"), "ev_revenue": Decimal("1.5"), "pe": Decimal("14")},
    "advertising-agency": {
        "ev_ebitda": Decimal("4.8"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("14"),
    },
    "animation": {"ev_ebitda": Decimal("4.2"), "ev_revenue": Decimal("1.3"), "pe": Decimal("13")},
    "content-creation": {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("1.2"),
        "pe": Decimal("13"),
    },
    "music-production": {
        "ev_ebitda": Decimal("3.8"),
        "ev_revenue": Decimal("1.1"),
        "pe": Decimal("13"),
    },
    "printing": {"ev_ebitda": Decimal("3.0"), "ev_revenue": Decimal("0.7"), "pe": Decimal("11")},
    "social-media": {
        "ev_ebitda": Decimal("4.2"),
        "ev_revenue": Decimal("1.3"),
        "pe": Decimal("13"),
    },
    "videography": {"ev_ebitda": Decimal("3.8"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    # NACE 59.11. Project-based and working-capital heavy, so it sits just below
    # animation/content-creation unless an owned library is evidenced separately.
    "film-tv-production": {
        "ev_ebitda": Decimal("3.9"),
        "ev_revenue": Decimal("1.0"),
        "pe": Decimal("13"),
    },
    # ── MISC / LEGACY ALIASES ─────────────────────────────────────
    "security": {"ev_ebitda": Decimal("4.0"), "ev_revenue": Decimal("1.2"), "pe": Decimal("13")},
    "property-management": {
        "ev_ebitda": Decimal("5.5"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("15"),
    },
    "antiques": {"ev_ebitda": Decimal("3.2"), "ev_revenue": Decimal("0.8"), "pe": Decimal("12")},
    "gift-shop": {"ev_ebitda": Decimal("3.4"), "ev_revenue": Decimal("0.9"), "pe": Decimal("12")},
}

# Industry defaults (SME-calibrated: Pepperdine 2024, BizBuySell)
INDUSTRY_DEFAULTS = {
    "technology": {"ev_ebitda": Decimal("7.0"), "pe": Decimal("18")},
    "professional-services": {"ev_ebitda": Decimal("5.5"), "pe": Decimal("14")},
    "food-beverage": {"ev_ebitda": Decimal("3.5"), "pe": Decimal("12")},
    "manufacturing": {"ev_ebitda": Decimal("4.5"), "pe": Decimal("12")},
    "retail": {"ev_ebitda": Decimal("4.0"), "pe": Decimal("12")},
    "services": {"ev_ebitda": Decimal("5.0"), "pe": Decimal("13")},
    "environmental-services": {"ev_ebitda": Decimal("4.5"), "pe": Decimal("12")},
}
