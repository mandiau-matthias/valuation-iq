"""Resolve valuation business-type categories from Titan, DB, and fallback inputs."""

from __future__ import annotations

from typing import Callable, Mapping, Optional, Protocol, Sequence, TypeVar


class CategoryLike(Protocol):
    """Enum-like category value used in triage logs and responses."""

    @property
    def value(self) -> str:
        """Stable serialized category value."""


CategoryT = TypeVar("CategoryT", bound=CategoryLike)


class TriageLogger(Protocol):
    """Logger surface needed by the category resolver."""

    def debug(self, message: str, *args: object, **kwargs: object) -> None:
        """Log debug-level category decisions."""

    def warning(self, message: str, *args: object, **kwargs: object) -> None:
        """Log recoverable category resolution failures."""


class MetricCounter(Protocol):
    """Prometheus counter child returned by labels()."""

    def inc(self) -> None:
        """Increment the metric counter."""


class DerivationMetric(Protocol):
    """Metric used to track category derivation source."""

    def labels(self, **labels: str) -> MetricCounter:
        """Return a labeled counter child."""


IndustryCategoryFallbacks = Sequence[tuple[Sequence[str], CategoryT]]


def _increment_derivation_metric(
    metric: DerivationMetric | None,
    source: str,
) -> None:
    if metric is not None:
        metric.labels(source=source).inc()


def map_industry_text_to_category(
    industry_text: str,
    rules: IndustryCategoryFallbacks[CategoryT],
) -> Optional[CategoryT]:
    """Map free-text industry labels to a category using ordered keyword rules."""
    industry_lower = industry_text.lower()
    for tokens, category in rules:
        if any(token in industry_lower for token in tokens):
            return category
    return None


def resolve_business_type_category(
    *,
    business_type_id: Optional[str],
    business_model: Optional[str],
    industry: Optional[str],
    category_id: Optional[str],
    category_id_to_enum: Mapping[str, CategoryT],
    business_type_categories: Mapping[str, CategoryT],
    industry_category_fallbacks: IndustryCategoryFallbacks[CategoryT],
    map_industry_to_category: Callable[[str], Optional[CategoryT]],
    logger: TriageLogger,
    derivation_metric: DerivationMetric | None,
    other_category: CategoryT,
) -> CategoryT:
    """Determine business type category without coupling the engine to lookup details."""

    if category_id:
        category_id_normalized = category_id.lower().strip()

        if category_id_normalized in category_id_to_enum:
            category = category_id_to_enum[category_id_normalized]
            logger.debug(
                f"✅ Business type category from TITAN ENRICHMENT: {category_id} → {category.value}",
                extra={
                    "category_id": category_id,
                    "business_type_id": business_type_id,
                    "source": "titan_enrichment",
                },
            )
            _increment_derivation_metric(derivation_metric, "titan_enrichment")
            return category
        logger.warning(
            f"⚠️ category_id '{category_id}' not found in CATEGORY_ID_TO_ENUM mapping, falling back to other methods",
            extra={"category_id": category_id, "business_type_id": business_type_id},
        )

    if business_type_id:
        try:
            from src.database.business_types_repository import get_business_types_repository

            with get_business_types_repository() as repo:
                business_type = repo.get_business_type(business_type_id)

                if business_type:
                    business_type_industry = getattr(business_type, "industry", None)
                    if business_type_industry:
                        category = map_industry_to_category(str(business_type_industry).lower())
                        if category:
                            logger.debug(
                                f"✅ Business type category found via DATABASE lookup: {business_type_id} → {category.value}",
                                extra={
                                    "business_type_id": business_type_id,
                                    "industry": business_type_industry,
                                    "source": "database_primary",
                                },
                            )
                            _increment_derivation_metric(derivation_metric, "database")
                            return category

                    industry_mapping = getattr(business_type, "industry_mapping", None)
                    if industry_mapping:
                        category = map_industry_to_category(str(industry_mapping).lower())
                        if category:
                            logger.debug(
                                f"✅ Business type category found via DATABASE industry_mapping: {business_type_id} → {category.value}",
                                extra={
                                    "business_type_id": business_type_id,
                                    "industry_mapping": industry_mapping,
                                    "source": "database_secondary",
                                },
                            )
                            return category

                    database_category_id = getattr(business_type, "category_id", None)
                    if database_category_id:
                        cat_id = str(database_category_id).lower()
                        category = category_id_to_enum.get(cat_id) or category_id_to_enum.get(
                            cat_id.replace("-", "_")
                        )
                        if category:
                            logger.debug(
                                f"✅ Business type category found via DATABASE category_id: {business_type_id} → {category.value}",
                                extra={
                                    "business_type_id": business_type_id,
                                    "category_id": database_category_id,
                                    "source": "database_category_id",
                                },
                            )
                            return category

                    logger.debug(
                        f"Business type found in database but no category mapping: {business_type_id}",
                        extra={"business_type_id": business_type_id},
                    )
        except Exception as exc:
            logger.warning(
                f"⚠️ Database lookup failed for business_type_id '{business_type_id}', falling back to static mapping: {exc}",
                extra={
                    "business_type_id": business_type_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

        category = business_type_categories.get(business_type_id)
        if category:
            logger.debug(
                f"ℹ️ Business type category found via STATIC FALLBACK: {business_type_id} → {category.value}",
                extra={
                    "business_type_id": business_type_id,
                    "category": category.value,
                    "source": "static_fallback",
                },
            )
            _increment_derivation_metric(derivation_metric, "static_fallback")
            return category

    if business_model:
        business_model_lower = business_model.lower()
        generic_models = {"service", "services", "business", "company", "unknown", "other"}
        if business_model_lower not in generic_models:
            for bt_id, category in business_type_categories.items():
                if bt_id == business_model_lower or bt_id in business_model_lower:
                    logger.debug(
                        f"Business type category found via fuzzy match: {business_model} → {category.value}",
                        extra={"business_model": business_model, "category": category.value},
                    )
                    return category

    if industry:
        industry_lower = industry.lower()
        for tokens, category in industry_category_fallbacks:
            if any(token in industry_lower for token in tokens):
                return category

    logger.warning(
        "Could not determine business type category, using OTHER (fallback)",
        extra={
            "business_type_id": business_type_id,
            "business_model": business_model,
            "industry": industry,
        },
    )
    return other_category
