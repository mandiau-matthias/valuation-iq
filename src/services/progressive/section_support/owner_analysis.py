"""Owner dependency helpers for progressive valuation sections."""

from __future__ import annotations

from typing import TypedDict


class OwnerFactor(TypedDict):
    name: str
    score: int
    description: str


def calculate_owner_dependency_factors() -> tuple[list[OwnerFactor], int]:
    """Calculate owner dependency factors and total score."""
    dependency_factors = [
        {
            "name": "Client Relationships",
            "score": 8,
            "description": "Owner maintains primary client relationships",
        },
        {
            "name": "Daily Operations",
            "score": 7,
            "description": "Owner involved in day-to-day decision making",
        },
        {
            "name": "Sales & Business Development",
            "score": 9,
            "description": "Owner drives majority of new business",
        },
        {
            "name": "Technical Expertise",
            "score": 6,
            "description": "Owner provides specialized knowledge and expertise",
        },
    ]
    total_dependency = sum(factor["score"] for factor in dependency_factors)
    return dependency_factors, total_dependency


def calculate_owner_discount(dependency_score: int) -> float:
    """Calculate owner discount based on dependency score."""
    if dependency_score > 75:
        return 25.0
    if dependency_score > 50:
        return 15.0
    if dependency_score > 25:
        return 8.0
    return 3.0


def calculate_transition_readiness_scores(
    dependency_score: int,
    employees: int,
    client_score: int,
) -> dict[str, int]:
    """Calculate transition readiness scores."""
    return {
        "documentation_score": max(0, 100 - dependency_score),
        "team_capability_score": min(int((employees / 20) * 100), 100),
        "systems_score": max(0, 100 - dependency_score + 10),
        "client_relationships_score": max(0, 100 - client_score * 10),
    }


def get_exit_readiness_message(dependency_score: int) -> str:
    """Get exit readiness message based on dependency score."""
    if dependency_score > 70:
        return (
            "High owner dependency significantly impacts business value. Implementing "
            "transition strategies over 12-18 months could increase valuation by 20-30%."
        )
    if dependency_score > 40:
        return (
            "Moderate owner dependency creates some buyer concerns. Focused "
            "improvements in key areas could enhance valuation by 10-15%."
        )
    return (
        "Business demonstrates strong transition readiness with limited owner "
        "dependency. Well-positioned for successful exit."
    )


def get_owner_recommendations() -> list[str]:
    """Get standard owner dependency recommendations."""
    return [
        "Document all key processes and procedures",
        "Develop and empower management team",
        "Transition client relationships to account managers",
        "Implement CRM and business management systems",
        "Create succession plan with defined timeline",
        "Build institutional knowledge base",
    ]
