"""
Summary Generation Coordinator

Coordinates executive summary and recommendations generation.
"""

import logging
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from src.domain.multiples.strength_factor_discount_evidence import (
    strength_factor_discount_adjustments_from_business_context,
)

logger = logging.getLogger(__name__)


_STRENGTHENING_ACTIONS: dict[str, tuple[str, str]] = {
    "owner_dependency": (
        "reduce owner dependency",
        "documenting owner-critical routines, assigning named backup coverage, and moving client or production decisions into repeatable roles",
    ),
    "owner_dependence": (
        "reduce owner dependency",
        "documenting owner-critical routines, assigning named backup coverage, and moving client or production decisions into repeatable roles",
    ),
    "owner_hours_dependency": (
        "reduce owner dependency",
        "documenting owner-critical routines, assigning named backup coverage, and moving client or production decisions into repeatable roles",
    ),
    "customer_concentration": (
        "lower customer concentration risk",
        "broadening revenue across named customers and evidencing contract renewals or account handovers",
    ),
    "recurring_revenue_quality": (
        "strengthen recurring revenue quality",
        "evidencing contracted recurring revenue, churn, and renewal quality before relying on a higher market multiple",
    ),
    "revenue_quality": (
        "strengthen revenue quality",
        "separating recurring, project, and one-off revenue so the advisor can retest the applied liquidity discount",
    ),
    "financial_cleanliness": (
        "strengthen financial cleanliness",
        "cleaning add-backs, reconciling management accounts, and attaching source documents for buyer-verifiable earnings",
    ),
    "management_depth": (
        "build management depth",
        "giving second-line managers ownership of critical workflows and evidencing decision rights beyond the seller",
    ),
    "moat_differentiation": (
        "strengthen competitive differentiation",
        "evidencing repeatable advantages such as proprietary process, contract protection, brand pull, or defensible niche positioning",
    ),
    "margin_context": (
        "strengthen margin durability",
        "separating sustainable margin drivers from temporary price, cost, or owner-effort effects",
    ),
    "margin_quality": (
        "strengthen margin durability",
        "separating sustainable margin drivers from temporary price, cost, or owner-effort effects",
    ),
    "operating_quality": (
        "strengthen operating quality",
        "evidencing process stability, staffing resilience, and repeatable delivery quality",
    ),
    "working_capital": (
        "normalize working-capital evidence",
        "proving receivable, inventory, and payable patterns so the advisor can separate operating drag from deal structure",
    ),
    "platform_dependency": (
        "reduce platform dependency",
        "showing channel diversification, owned customer access, and contingency options for platform-policy risk",
    ),
}


class SummaryGenerationCoordinator:
    """
    Coordinates executive summary and recommendations generation.
    """

    def __init__(self) -> None:
        """Initialize the summary generation coordinator."""
        self.logger = logger

    @staticmethod
    def _as_float(value: object, default: float = 0.0) -> float:
        if not isinstance(value, (Decimal, float, int, str)):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _format_currency_value(value: object) -> str:
        try:
            return f"{Decimal(str(value)):,.0f}"
        except (InvalidOperation, ValueError):
            return "0"

    def generate_executive_summary(
        self,
        data: Mapping[str, object],
        final_valuation: Mapping[str, object],
    ) -> str:
        """
        Generate executive summary for final valuation.

        Args:
            data: Dictionary with company data
            final_valuation: Dictionary with final valuation results

        Returns:
            Executive summary string
        """
        company_name = data.get("company_name", "the business")
        value_mid = self._format_currency_value(final_valuation.get("value_mid", 0))

        return f"""
        Based on our comprehensive analysis, {company_name} has an estimated equity value
        of €{value_mid}. This valuation incorporates industry benchmarks, financial performance,
        market conditions, and business-specific factors. The analysis provides a solid foundation
        for strategic decision-making and potential transactions.
        """

    def generate_recommendations(
        self,
        data: Mapping[str, object],
        owner_analysis: Mapping[str, object],
    ) -> list[str]:
        """
        Generate recommendations based on owner analysis and data.

        Args:
            data: Dictionary with company data
            owner_analysis: Dictionary with owner analysis results

        Returns:
            List of recommendation strings
        """
        evidence_backed = self.generate_strength_factor_recommendations(data)
        if evidence_backed:
            return evidence_backed

        recommendations = []

        # Add recommendations based on owner analysis
        dependency_score = self._as_float(owner_analysis.get("dependency_score", 0.0))
        if dependency_score > 0.7:
            recommendations.append(
                "Consider implementing succession planning to reduce owner dependency"
            )

        if owner_analysis.get("transferability_risk") == "High":
            recommendations.append("Focus on documenting processes and building management team")

        # Add general recommendations
        recommendations.extend(
            [
                "Maintain detailed financial records for future valuations",
                "Consider professional business advisory services",
                "Regularly review and update business valuation",
            ]
        )

        return recommendations

    def generate_strength_factor_recommendations(self, data: Mapping[str, object]) -> list[str]:
        """Generate recommendations backed by strength-factor or maturity evidence."""
        business_context = self._business_context(data)
        explicit_rows = self._explicit_strength_factor_evidence_rows(business_context)
        recommendations = self._strength_factor_recommendations_from_rows(explicit_rows)
        if recommendations:
            return recommendations

        maturity_recommendations = self._growth_maturity_recommendations(data)
        if maturity_recommendations:
            return maturity_recommendations

        derived_rows = strength_factor_discount_adjustments_from_business_context(
            business_context
        )
        return self._strength_factor_recommendations_from_rows(derived_rows)

    def generate_phase_recommendations(
        self,
        data: Mapping[str, object],
        owner_analysis: Mapping[str, object],
        valuation_recommendations: object,
    ) -> list[str]:
        evidence_backed = self.generate_strength_factor_recommendations(data)
        if evidence_backed:
            return evidence_backed

        fallback = self._normalize_recommendations(valuation_recommendations)
        if fallback:
            return fallback

        return self.generate_recommendations(data, owner_analysis)

    def _strength_factor_recommendations(self, data: Mapping[str, object]) -> list[str]:
        business_context = self._business_context(data)
        evidence_rows = self._strength_factor_evidence_rows(business_context)
        return self._strength_factor_recommendations_from_rows(evidence_rows)

    def _strength_factor_recommendations_from_rows(
        self,
        evidence_rows: Sequence[Mapping[str, object]],
    ) -> list[str]:
        if not evidence_rows:
            return []

        recommendations: list[str] = []
        seen: set[tuple[str, str]] = set()
        for row in evidence_rows:
            factor_key = self._primary_factor_key(row)
            discount_key = self._discount_key(row)
            dedupe_key = (factor_key, discount_key)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            action_label, owner_action = self._strengthening_action(factor_key, row)
            data_point_ids = self._data_point_ids(row)
            advisor_action = self._advisor_action(discount_key, data_point_ids)
            recommendations.append(
                f"Owner action: {action_label} - {owner_action}. "
                f"Advisor action: {advisor_action}."
            )
            if len(recommendations) >= 5:
                break
        return recommendations

    def _explicit_strength_factor_evidence_rows(
        self,
        business_context: Mapping[str, object],
    ) -> list[Mapping[str, object]]:
        rows: list[Mapping[str, object]] = []
        for key in (
            "strength_factor_discount_adjustments",
            "strength_factor_discount_evidence",
            "strength_factor_multiple_adjustments",
        ):
            rows.extend(self._raw_strength_factor_rows(business_context.get(key)))
        return rows

    def _growth_maturity_recommendations(self, data: Mapping[str, object]) -> list[str]:
        business_context = self._business_context(data)
        maturity = business_context.get("business_growth_maturity")
        if not isinstance(maturity, Mapping):
            return []

        rows = maturity.get("stage_challenges")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            return []

        stage_label = (
            self._text(maturity.get("effective_stage_label"))
            or self._text(maturity.get("effective_stage"))
            or "current stage"
        )
        maturity_data_points = self._growth_maturity_data_points(maturity)
        recommendations: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            todo = self._text(row.get("todo"))
            if not todo:
                continue
            row_key = self._text(row.get("key")) or todo
            if row_key in seen:
                continue
            seen.add(row_key)

            action_label = self._growth_maturity_action_label(stage_label, row_key)
            data_points = [
                *self._text_list(row.get("data_point_ids")),
                *maturity_data_points,
            ]
            data_points = list(dict.fromkeys(data_points))
            advisor_action = self._growth_maturity_advisor_action(data_points)
            recommendations.append(
                f"Owner action: {action_label} - {todo.rstrip('.')}. "
                f"Advisor action: {advisor_action}."
            )
            if len(recommendations) >= 3:
                break
        return recommendations

    def _growth_maturity_data_points(self, maturity: Mapping[str, object]) -> list[str]:
        points: list[str] = []
        for key in ("revenue_stage", "team_stage", "effective_stage", "alignment"):
            value = self._text(maturity.get(key))
            if value:
                points.append(f"business_growth_maturity.{key}={value}")
        return points

    @staticmethod
    def _growth_maturity_action_label(stage_label: str, row_key: str) -> str:
        normalized_key = row_key.lower().replace("-", "_").replace(" ", "_")
        if normalized_key.startswith("team_capacity_"):
            return "rebalance revenue and team maturity"
        return f"strengthen {stage_label.lower()} operating system"

    def _growth_maturity_advisor_action(self, data_points: Sequence[str]) -> str:
        points = ", ".join(data_points[:4])
        suffix = f" after strengthening data points {points}" if points else ""
        return f"retest growth maturity and multiple-discount assumptions{suffix}"

    def _strength_factor_evidence_rows(
        self,
        business_context: Mapping[str, object],
    ) -> list[Mapping[str, object]]:
        rows: list[Mapping[str, object]] = [
            *strength_factor_discount_adjustments_from_business_context(business_context)
        ]
        rows.extend(self._explicit_strength_factor_evidence_rows(business_context))
        return rows

    def _raw_strength_factor_rows(self, value: object) -> list[Mapping[str, object]]:
        if isinstance(value, Mapping):
            nested_rows: list[Mapping[str, object]] = []
            for key in ("rows", "adjustments", "evidence"):
                nested_rows.extend(self._raw_strength_factor_rows(value.get(key)))
            if nested_rows:
                return nested_rows
            return [value] if self._is_strength_factor_row(value) else []

        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return []

        rows: list[Mapping[str, object]] = []
        for item in value:
            rows.extend(self._raw_strength_factor_rows(item))
        return rows

    def _is_strength_factor_row(self, row: Mapping[str, object]) -> bool:
        return any(
            self._has_value(row.get(key))
            for key in (
                "factor_key",
                "factorKey",
                "factor_label",
                "factorLabel",
                "improvement_action",
                "improvementAction",
                "valuation_linkage",
                "valuationLinkage",
                "discount_key",
                "discountKey",
                "multiple_discount_key",
                "multipleDiscountKey",
                "data_point_id",
                "dataPointId",
                "data_point_ids",
                "dataPointIds",
                "dataPoints",
            )
        )

    @staticmethod
    def _business_context(data: Mapping[str, object]) -> Mapping[str, object]:
        merged: dict[str, object] = dict(data)
        for key in ("business_context", "metadata", "multiples_metadata"):
            value = data.get(key)
            if isinstance(value, Mapping):
                merged.update(value)
        return merged

    def _primary_factor_key(self, row: Mapping[str, object]) -> str:
        for key in (
            "factor_key",
            "factorKey",
            "mapped_subjective_input",
            "mappedSubjectiveInput",
            "captured_input_id",
            "capturedInputId",
            "discount_key",
            "discountKey",
        ):
            value = self._text(row.get(key))
            if value:
                return value
        data_points = self._data_point_ids(row)
        if data_points:
            return data_points[0].split(".")[-1]
        return "strength_factor"

    def _discount_key(self, row: Mapping[str, object]) -> str:
        linkage = self._linkage(row)
        for source in (row, linkage):
            for key in (
                "multiple_discount_key",
                "multipleDiscountKey",
                "discount_key",
                "discountKey",
            ):
                value = self._text(source.get(key))
                if value:
                    return value
        return "multiple_discount"

    def _strengthening_action(
        self,
        factor_key: str,
        row: Mapping[str, object],
    ) -> tuple[str, str]:
        action = self._seed_improvement_action(row)
        if action:
            return action

        normalized_key = factor_key.lower().replace("-", "_").replace(" ", "_")
        if normalized_key in _STRENGTHENING_ACTIONS:
            return _STRENGTHENING_ACTIONS[normalized_key]

        label = (
            self._text(row.get("factor_label"))
            or normalized_key.replace("_", " ")
            or "captured strength factor"
        )
        return (
            f"strengthen {label}",
            "improving the captured data point and attaching buyer-verifiable evidence before rerunning the valuation",
        )

    def _seed_improvement_action(self, row: Mapping[str, object]) -> tuple[str, str] | None:
        raw_action = row.get("improvement_action") or row.get("improvementAction")
        if not isinstance(raw_action, Mapping):
            return None
        title = self._text(raw_action.get("title"))
        summary = self._text(raw_action.get("summary"))
        if not title or not summary:
            return None
        return title, summary.rstrip(".")

    def _advisor_action(self, discount_key: str, data_point_ids: Sequence[str]) -> str:
        points = ", ".join(data_point_ids[:4])
        suffix = f" after strengthening data points {points}" if points else ""
        return f"retest `{discount_key}`{suffix}"

    @staticmethod
    def _text(value: object) -> str:
        return value.strip() if isinstance(value, str) and value.strip() else ""

    @staticmethod
    def _has_value(value: object) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, Mapping):
            return bool(value)
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            return bool(value)
        return value is not None

    @staticmethod
    def _linkage(row: Mapping[str, object]) -> Mapping[str, object]:
        for key in ("valuation_linkage", "valuationLinkage"):
            value = row.get(key)
            if isinstance(value, Mapping):
                return value
        return {}

    def _data_point_ids(self, row: Mapping[str, object]) -> list[str]:
        direct = [
            *self._text_list(row.get("data_point_ids")),
            *self._text_list(row.get("dataPointIds")),
        ]
        if direct:
            return list(dict.fromkeys(direct))[:8]

        points = row.get("dataPoints")
        if not isinstance(points, Sequence) or isinstance(points, (str, bytes, bytearray)):
            return []

        ids: list[str] = []
        for point in points:
            if not isinstance(point, Mapping):
                continue
            for key in ("dataPointId", "data_point_id", "questionId", "question_id"):
                value = self._text(point.get(key))
                if value:
                    ids.append(value)
                    break
        return list(dict.fromkeys(ids))[:8]

    def _text_list(self, value: object) -> list[str]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return []
        return [text for item in value if (text := self._text(item))]

    @staticmethod
    def _normalize_recommendations(value: object) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return []
