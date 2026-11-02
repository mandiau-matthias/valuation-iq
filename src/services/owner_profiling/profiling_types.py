"""
Enhanced Owner Profiling Types

This module contains all data structures, enums, and type definitions
for the enhanced owner profiling engine.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class RiskLevel(str, Enum):
    """Owner dependency risk levels"""
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TechnicalRequirement:
    """Technical requirement for business operation"""
    skill_name: str
    importance_level: int  # 1-10
    rarity_score: int  # 1-10 (10 = very rare)
    certification_required: bool
    training_time_months: int


@dataclass
class OwnerRiskAssessment:
    """Comprehensive owner risk assessment"""
    overall_risk_score: Decimal
    risk_level: RiskLevel

    # Detailed risk categories
    time_commitment_risk: Decimal
    technical_requirements_risk: Decimal
    delegation_capability_risk: Decimal
    succession_planning_risk: Decimal

    # Risk factors
    risk_factors: List[str]
    mitigation_recommendations: List[str]

    # Due diligence notes
    due_diligence_notes: str
    valuation_impact: str
    transferability_assessment: str


@dataclass
class OwnerRiskAssessmentReport:
    """Comprehensive owner risk assessment report for due diligence"""

    # Basic Information
    owner_name: str
    business_name: str
    assessment_date: datetime

    # Risk Scores
    overall_risk_score: Decimal
    risk_level: str

    # Detailed Risk Categories
    time_commitment_risk: Decimal
    technical_requirements_risk: Decimal
    delegation_capability_risk: Decimal
    succession_planning_risk: Decimal

    # Owner Profile Details
    hours_per_week: int
    delegation_capability: int
    succession_plan: bool
    technical_skills: List[str]
    certifications: List[str]

    # Risk Factors
    risk_factors: List[str]
    mitigation_recommendations: List[str]

    # Due Diligence Notes
    due_diligence_notes: str
    valuation_impact: str
    transferability_assessment: str

    # Recommendations
    immediate_actions: List[str]
    long_term_improvements: List[str]
    valuation_adjustments: List[str]


# Default question templates
OWNER_QUESTIONS = {
    "time_commitment": [
        {
            "question": "How many hours per week do you personally spend on the business?",
            "field": "owner_hours_per_week",
            "type": "number",
            "validation": "0-168",
            "risk_weight": Decimal('0.4'),
            "follow_up": "What percentage of your time is spent on operations vs management?"
        },
        {
            "question": "Do you work weekends or holidays?",
            "field": "weekend_work",
            "type": "boolean",
            "risk_weight": Decimal('0.2'),
            "follow_up": "How many vacation days do you take per year?"
        },
        {
            "question": "Are there specific periods when you work more hours?",
            "field": "peak_periods",
            "type": "text",
            "risk_weight": Decimal('0.1'),
            "follow_up": "How do you handle these peak periods?"
        }
    ],
    "technical_requirements": [
        {
            "question": "What specific technical skills are required to run this business?",
            "field": "technical_skills_required",
            "type": "multi_select",
            "options": "industry_specific_skills",
            "risk_weight": Decimal('0.5'),
            "follow_up": "How difficult would it be to find someone with these skills?"
        },
        {
            "question": "Do you have any specialized certifications or licenses?",
            "field": "owner_certifications",
            "type": "multi_select",
            "risk_weight": Decimal('0.3'),
            "follow_up": "Are these certifications required to operate the business?"
        },
        {
            "question": "What equipment or systems do you personally operate?",
            "field": "equipment_operation",
            "type": "multi_select",
            "risk_weight": Decimal('0.4'),
            "follow_up": "How much training would someone need to operate this equipment?"
        }
    ],
    "delegation_capability": [
        {
            "question": "On a scale of 1-10, how well can you delegate tasks?",
            "field": "delegation_capability",
            "type": "scale_1_10",
            "risk_weight": Decimal('0.4'),
            "follow_up": "What types of tasks do you find hardest to delegate?"
        },
        {
            "question": "Do you have managers who can run the business without you?",
            "field": "management_structure",
            "type": "boolean",
            "risk_weight": Decimal('0.3'),
            "follow_up": "How many years of experience do they have?"
        },
        {
            "question": "Who are your key employees and what do they do?",
            "field": "key_personnel",
            "type": "text",
            "risk_weight": Decimal('0.3'),
            "follow_up": "Could they run the business if you were unavailable?"
        }
    ],
    "succession_planning": [
        {
            "question": "Do you have a succession plan in place?",
            "field": "succession_plan",
            "type": "boolean",
            "risk_weight": Decimal('0.4'),
            "follow_up": "Who would take over if you were unavailable?"
        },
        {
            "question": "How much of your knowledge is documented?",
            "field": "knowledge_documentation",
            "type": "percentage",
            "risk_weight": Decimal('0.3'),
            "follow_up": "What key processes are documented?"
        },
        {
            "question": "What happens if you're unavailable for extended periods?",
            "field": "business_continuity",
            "type": "text",
            "risk_weight": Decimal('0.3'),
            "follow_up": "How long could the business operate without you?"
        }
    ],
    "customer_relationships": [
        {
            "question": "How many of your customer relationships depend on you personally?",
            "field": "customer_dependency",
            "type": "percentage",
            "risk_weight": Decimal('0.4'),
            "follow_up": "Which customers know only you?"
        },
        {
            "question": "Do you have key customer relationships that only you manage?",
            "field": "key_customer_relationships",
            "type": "boolean",
            "risk_weight": Decimal('0.3'),
            "follow_up": "How important are these relationships to the business?"
        }
    ],
    "supplier_relationships": [
        {
            "question": "How many of your supplier relationships depend on you personally?",
            "field": "supplier_dependency",
            "type": "percentage",
            "risk_weight": Decimal('0.3'),
            "follow_up": "Which suppliers know only you?"
        },
        {
            "question": "Do you have key supplier relationships that only you manage?",
            "field": "key_supplier_relationships",
            "type": "boolean",
            "risk_weight": Decimal('0.2'),
            "follow_up": "How important are these relationships to the business?"
        }
    ]
}


# Industry-specific technical requirements
TECHNICAL_REQUIREMENTS = {
    "brewing": {
        "technical_skills": [
            "Brewing process knowledge",
            "Quality control expertise",
            "Equipment maintenance",
            "Recipe development",
            "Regulatory compliance",
            "Taste testing and quality assurance",
            "Fermentation management",
            "Packaging and labeling"
        ],
        "certifications": [
            "Brewing certifications",
            "Food safety training",
            "HACCP certification",
            "Alcohol licensing",
            "Health department compliance"
        ],
        "equipment_knowledge": [
            "Brewing equipment operation",
            "Maintenance procedures",
            "Troubleshooting skills",
            "Equipment upgrades and modifications"
        ],
        "regulatory_requirements": [
            "Food safety regulations",
            "Alcohol licensing",
            "Health department compliance",
            "Environmental regulations"
        ]
    },
    "manufacturing": {
        "technical_skills": [
            "Production process knowledge",
            "Quality control systems",
            "Equipment operation",
            "Safety protocols",
            "Process optimization",
            "Maintenance procedures"
        ],
        "certifications": [
            "Manufacturing certifications",
            "Safety training",
            "Quality management",
            "ISO certifications",
            "Environmental compliance"
        ],
        "equipment_knowledge": [
            "Production equipment operation",
            "Maintenance procedures",
            "Safety protocols",
            "Equipment troubleshooting"
        ]
    },
    "technology": {
        "technical_skills": [
            "Software development",
            "System architecture",
            "Database management",
            "Security protocols",
            "DevOps processes",
            "Product development",
            "Technical support",
            "System maintenance"
        ],
        "certifications": [
            "Technical certifications",
            "Industry standards",
            "Security protocols",
            "Cloud computing",
            "Data protection"
        ],
        "equipment_knowledge": [
            "Development tools",
            "Server management",
            "Network infrastructure",
            "Security systems"
        ]
    },
    "services": {
        "technical_skills": [
            "Service delivery expertise",
            "Client management",
            "Process optimization",
            "Quality assurance",
            "Customer service",
            "Project management"
        ],
        "certifications": [
            "Professional certifications",
            "Industry standards",
            "Client requirements",
            "Quality management",
            "Customer service"
        ],
        "equipment_knowledge": [
            "Service delivery tools",
            "Client management systems",
            "Quality assurance equipment",
            "Communication systems"
        ]
    }
}


# Risk assessment rules
RISK_ASSESSMENT_RULES = {
    "time_commitment_risk": {
        "very_high": {"threshold": 50, "score": 0.9},
        "high": {"threshold": 40, "score": 0.7},
        "medium": {"threshold": 30, "score": 0.5},
        "low": {"threshold": 0, "score": 0.2}
    },
    "delegation_capability_risk": {
        "very_high": {"threshold": 3, "score": 0.9},
        "high": {"threshold": 5, "score": 0.7},
        "medium": {"threshold": 7, "score": 0.5},
        "low": {"threshold": 10, "score": 0.2}
    },
    "technical_requirements_risk": {
        "very_high": {"threshold": 8, "score": 0.9},
        "high": {"threshold": 6, "score": 0.7},
        "medium": {"threshold": 4, "score": 0.5},
        "low": {"threshold": 2, "score": 0.2}
    },
    "succession_planning_risk": {
        "high": {"has_plan": False, "score": 0.8},
        "low": {"has_plan": True, "score": 0.2}
    }
}