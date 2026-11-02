"""Industry lookup helper for legacy valuation schemas."""

import logging
from typing import Set

logger = logging.getLogger(__name__)


def get_valid_industries() -> Set[str]:
    """
    Get valid industry values using static configuration.

    ValuationIQ is a stateless calculation engine. In stateless mode, we use a
    static list of valid industries; dynamic industry data should come from
    Titan via payload.
    """
    from src.database.connection import is_stateless_mode

    # Covers the published Delphi/Titan catalog plus common legacy aliases.
    static_industries = {
        "technology",
        "manufacturing",
        "retail",
        "services",
        "healthcare",
        "finance",
        "real_estate",
        "hospitality",
        "construction",
        "food-production",
        "food-services",
        "professional-services",
        "ecommerce",
        "other",
        "creative-media",
        "creativemedia",
        "advertising",
        "saas",
        "software",
        "software-development",
        "it-services",
        "fintech",
        "edtech",
        "healthtech",
        "proptech",
        "legaltech",
        "restaurant",
        "cafe",
        "bakery",
        "catering",
        "food-truck",
        "brewery",
        "winery",
        "distillery",
        "coffee-shop",
        "consulting",
        "legal",
        "accounting",
        "tax-services",
        "marketing",
        "design",
        "architecture",
        "engineering",
        "photography",
        "videography",
        "music",
        "entertainment",
        "fitness",
        "gym",
        "wellness",
        "spa",
        "beauty",
        "salon",
        "hairstyling",
        "barbershop",
        "massage",
        "cosmetics",
        "cleaning",
        "landscaping",
        "plumbing",
        "electrical",
        "hvac",
        "roofing",
        "painting",
        "renovation",
        "carpentry",
        "auto-repair",
        "auto-sales",
        "car-wash",
        "transportation",
        "logistics",
        "delivery",
        "moving",
        "storage",
        "pet-services",
        "pet-grooming",
        "veterinary",
        "pet-retail",
        "childcare",
        "education",
        "tutoring",
        "coaching",
        "training",
        "event-planning",
        "wedding",
        "insurance",
        "real-estate-agency",
        "property-management",
        "travel",
        "tourism",
        "hotel",
        "bnb",
        "vacation-rental",
        "agriculture",
        "farming",
        "nursery",
        "greenhouse",
        "printing",
        "signage",
        "packaging",
        "distribution",
        "wholesale",
        "import-export",
        "marketplace",
        "gaming",
        "esports",
        "streaming",
        "content-creation",
    }

    if is_stateless_mode():
        # DEBUG: fires twice per request because the caller invokes
        # get_valid_industries() once for sanity-check and once for the
        # actual lookup. Demoted — stateless mode itself is reported at INFO
        # by the startup banner.
        logger.debug(
            "[GET-VALID-INDUSTRIES] STATELESS_MODE: Using static list with %s industries",
            len(static_industries),
        )
        return static_industries

    try:
        from sqlalchemy import text
        from src.database.connection import BusinessTypesSessionLocal

        if BusinessTypesSessionLocal is None:
            logger.debug(
                "[GET-VALID-INDUSTRIES] No DB connection, using static list with %s industries",
                len(static_industries),
            )
            return static_industries

        db = BusinessTypesSessionLocal()
        try:
            query = text(
                """
                SELECT DISTINCT industry
                FROM business_types
                WHERE status = 'active'
                  AND industry IS NOT NULL
                  AND industry != ''
            """
            )
            result = db.execute(query)
            db_industries = {row.industry for row in result.fetchall()}
            merged_industries = db_industries | static_industries

            logger.info(
                "Loaded %s industries for validation (DB + static)",
                len(merged_industries),
            )
            return merged_industries
        finally:
            db.close()

    except Exception as exc:
        logger.warning("Could not load industries from database, using static list: %s", exc)
        return static_industries
