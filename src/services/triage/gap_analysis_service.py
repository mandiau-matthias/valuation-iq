"""
Gap Analysis Service - Stateless Validation

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
This service provides VALIDATION logic only - no routing decisions.

THE MUSCLE ROLE (What this service does):
- Validates that required fields are present
- Identifies missing optional fields that would improve accuracy  
- Detects statistical anomalies (EBITDA margin deviations, etc.)
- Returns triage_flags for Titan to interpret
- Does NOT make routing decisions (that's Titan's job)
- Does NOT query the database (all data comes from request payload)

WHAT LIVES IN TITAN (The Brain):
- Deciding whether to route to Chat vs Manual UI (TriageService)
- Generating questions based on missing data (via Claude)
- Session state management
- User interaction flow

This service returns WHAT is missing, Titan decides HOW to collect it.

@author UpSwitch CTO Team
@version 2.0.0 - Brain & Muscle Stateless
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from src.domain.models import (
    ActionItem,
    DataSource,
    FieldMetadata,
    FieldStatus,
    GapAnalysisResult,
    InterfaceRoute,
    SessionFieldState,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# FIELD DEFINITIONS
# =============================================================================

# Fields that are required for calculation
REQUIRED_FIELDS = {
    "company_name": {"label": "Bedrijfsnaam", "weight": 1.0},
    "industry": {"label": "Sector", "weight": 1.0},
    "revenue": {"label": "Omzet", "weight": 1.0},
    "ebitda": {"label": "EBITDA", "weight": 1.0},
    "country_code": {"label": "Land", "weight": 0.8},
    "founding_year": {"label": "Oprichtingsjaar", "weight": 0.6},
}

# Fields that are optional but improve valuation quality
OPTIONAL_FIELDS = {
    "total_assets": {"label": "Totale activa", "weight": 0.5},
    "total_debt": {"label": "Totale schulden", "weight": 0.5},
    "cash": {"label": "Kas", "weight": 0.4},
    "employees": {"label": "Aantal medewerkers", "weight": 0.4},
    "number_of_owners": {"label": "Aantal eigenaren", "weight": 0.3},
    "business_type": {"label": "Type onderneming", "weight": 0.6},
    "business_model": {"label": "Business model", "weight": 0.4},
}

# Fields that require interpretation and should be routed to Chat
CHAT_ROUTED_FIELDS = {
    "owner_salary": {
        "label": "Eigenaarssalaris",
        "reason": "Requires market comparison for normalization",
    },
    "owner_salary_normalization": {
        "label": "Eigenaarssalaris normalisatie",
        "reason": "Requires interpretation of market rate",
    },
    "management_fee": {
        "label": "Management fee",
        "reason": "Requires context about operational vs non-operational",
    },
    "related_party_transactions": {
        "label": "Transacties met verbonden partijen",
        "reason": "Requires explanation of arm's length pricing",
    },
    "non_operational_costs": {
        "label": "Niet-operationele kosten",
        "reason": "Requires classification of cost types",
    },
    "exceptional_items": {
        "label": "Uitzonderlijke posten",
        "reason": "Requires interpretation of one-time events",
    },
    "rental_adjustment": {
        "label": "Huur normalisatie",
        "reason": "Requires market rate comparison",
    },
    "personal_expenses": {
        "label": "Persoonlijke kosten",
        "reason": "Requires identification of non-business expenses",
    },
}

# Fields that are simple and should be handled in Manual UI
MANUAL_ROUTED_FIELDS = {
    "company_name",
    "industry",
    "revenue",
    "ebitda",
    "country_code",
    "founding_year",
    "total_assets",
    "total_debt",
    "cash",
    "employees",
    "number_of_owners",
    "business_type",
    "business_model",
    "address",
    "legal_form",
    "vat_number",
    "kbo_number",
}

# Source confidence mappings
SOURCE_CONFIDENCE = {
    DataSource.KBO: 1.0,  # Registry data is authoritative
    DataSource.KVK: 1.0,  # Registry data is authoritative
    DataSource.IMPORT: 0.95,  # Accounting software is reliable
    DataSource.HISTORY: 0.8,  # Previous valuation data
    DataSource.USER_INPUT: 0.85,  # Manual entry by accountant
    DataSource.AI_SUGGESTED: 0.6,  # AI suggestions need review
}


class GapAnalysisService:
    """
    Analyzes data completeness and determines interface routing.

    This service implements the "Traffic Controller" pattern:
    1. Evaluates what data is available, uncertain, or missing
    2. Determines source attribution for each field
    3. Routes missing/uncertain data to Chat or Manual UI
    4. Generates prioritized action items
    """

    def __init__(self):
        """Initialize gap analysis service."""
        self.logger = logger

    def analyze(
        self,
        session_data: Dict[str, Any],
        field_sources: Optional[Dict[str, DataSource]] = None,
        existing_metadata: Optional[Dict[str, FieldMetadata]] = None,
    ) -> GapAnalysisResult:
        """
        Analyze session data and generate gap analysis result.

        Args:
            session_data: Current field values in the session
            field_sources: Optional mapping of field names to their data sources
            existing_metadata: Optional existing field metadata to preserve

        Returns:
            GapAnalysisResult with completeness score, action items, and routing
        """
        self.logger.info(
            "🔍 [GAP-ANALYSIS] Starting gap analysis",
            extra={
                "session_data_fields": list(session_data.keys()),
                "field_count": len(session_data),
            },
        )

        # Initialize field tracking
        fields_by_status: Dict[str, List[str]] = {
            "available": [],
            "uncertain": [],
            "missing": [],
            "normalized": [],
        }

        action_items: List[ActionItem] = []
        field_metadata: Dict[str, FieldMetadata] = existing_metadata or {}

        # Analyze required fields
        required_analysis = self._analyze_field_set(
            session_data=session_data,
            fields=REQUIRED_FIELDS,
            field_sources=field_sources,
            existing_metadata=existing_metadata,
            is_required=True,
        )

        # Analyze optional fields
        optional_analysis = self._analyze_field_set(
            session_data=session_data,
            fields=OPTIONAL_FIELDS,
            field_sources=field_sources,
            existing_metadata=existing_metadata,
            is_required=False,
        )

        # Merge results
        for status, fields in required_analysis["fields_by_status"].items():
            fields_by_status[status].extend(fields)
        for status, fields in optional_analysis["fields_by_status"].items():
            fields_by_status[status].extend(fields)

        action_items.extend(required_analysis["action_items"])
        action_items.extend(optional_analysis["action_items"])
        field_metadata.update(required_analysis["field_metadata"])
        field_metadata.update(optional_analysis["field_metadata"])

        # Check for normalization fields that need chat routing
        normalization_actions = self._check_normalization_fields(
            session_data=session_data,
            field_sources=field_sources,
        )
        action_items.extend(normalization_actions)

        # Sort action items by priority
        action_items.sort(key=lambda x: x.priority)

        # Calculate completeness score
        completeness_score = self._calculate_completeness_score(
            session_data=session_data,
            required_fields=REQUIRED_FIELDS,
            optional_fields=OPTIONAL_FIELDS,
        )

        # Determine if ready for calculation
        ready_for_calculation = self._is_ready_for_calculation(session_data)

        # Count actions by interface
        chat_action_count = sum(1 for a in action_items if a.interface == InterfaceRoute.CHAT)
        manual_action_count = sum(1 for a in action_items if a.interface == InterfaceRoute.MANUAL)

        result = GapAnalysisResult(
            completeness_score=completeness_score,
            ready_for_calculation=ready_for_calculation,
            fields_by_status=fields_by_status,
            action_items=action_items,
            available_count=len(fields_by_status["available"]),
            uncertain_count=len(fields_by_status["uncertain"]),
            missing_count=len(fields_by_status["missing"]),
            chat_action_count=chat_action_count,
            manual_action_count=manual_action_count,
            analyzed_at=datetime.utcnow(),
        )

        self.logger.info(
            "✅ [GAP-ANALYSIS] Analysis complete",
            extra={
                "completeness_score": completeness_score,
                "ready_for_calculation": ready_for_calculation,
                "available_count": result.available_count,
                "uncertain_count": result.uncertain_count,
                "missing_count": result.missing_count,
                "action_count": len(action_items),
                "chat_actions": chat_action_count,
                "manual_actions": manual_action_count,
            },
        )

        return result

    def _analyze_field_set(
        self,
        session_data: Dict[str, Any],
        fields: Dict[str, Dict[str, Any]],
        field_sources: Optional[Dict[str, DataSource]],
        existing_metadata: Optional[Dict[str, FieldMetadata]],
        is_required: bool,
    ) -> Dict[str, Any]:
        """
        Analyze a set of fields and determine their status.

        Returns:
            Dict with fields_by_status, action_items, and field_metadata
        """
        fields_by_status: Dict[str, List[str]] = {
            "available": [],
            "uncertain": [],
            "missing": [],
            "normalized": [],
        }
        action_items: List[ActionItem] = []
        field_metadata: Dict[str, FieldMetadata] = {}

        for field_name, field_config in fields.items():
            value = session_data.get(field_name)
            label = field_config.get("label", field_name)

            # Check existing metadata first
            if existing_metadata and field_name in existing_metadata:
                metadata = existing_metadata[field_name]
                fields_by_status[metadata.status.value].append(field_name)
                field_metadata[field_name] = metadata
                continue

            # Determine source
            source = DataSource.USER_INPUT
            if field_sources and field_name in field_sources:
                source = field_sources[field_name]

            # Determine status and create metadata
            if value is None or value == "":
                # Field is missing
                status = FieldStatus.MISSING
                confidence = 0.0
                fields_by_status["missing"].append(field_name)

                # Create action item for missing field
                interface = self._determine_interface(field_name)
                priority = 1 if is_required else 5

                action = ActionItem(
                    field=field_name,
                    field_label=label,
                    reason=f"{'Required' if is_required else 'Optional'} field is missing",
                    interface=interface,
                    priority=priority,
                    suggested_question=(
                        self._generate_question(field_name, label)
                        if interface == InterfaceRoute.CHAT
                        else None
                    ),
                )
                action_items.append(action)

            elif source == DataSource.AI_SUGGESTED:
                # AI-suggested values need review
                status = FieldStatus.UNCERTAIN
                confidence = SOURCE_CONFIDENCE.get(source, 0.6)
                fields_by_status["uncertain"].append(field_name)

                # Create action item for uncertain field
                action = ActionItem(
                    field=field_name,
                    field_label=label,
                    reason="AI-suggested value needs verification",
                    interface=InterfaceRoute.CHAT,
                    priority=2,
                    current_value=value,
                    suggested_question=f"Ik stel voor om {label} in te vullen als {value}. Is dit correct?",
                )
                action_items.append(action)

            else:
                # Field has a value from a trusted source
                status = FieldStatus.AVAILABLE
                confidence = SOURCE_CONFIDENCE.get(source, 0.85)
                fields_by_status["available"].append(field_name)

            # Create field metadata
            metadata = FieldMetadata(
                status=status,
                source=source,
                confidence=confidence,
                original_value=value,
                suggested_interface=self._determine_interface(field_name),
                last_updated=datetime.utcnow(),
            )
            field_metadata[field_name] = metadata

        return {
            "fields_by_status": fields_by_status,
            "action_items": action_items,
            "field_metadata": field_metadata,
        }

    def _check_normalization_fields(
        self,
        session_data: Dict[str, Any],
        field_sources: Optional[Dict[str, DataSource]],
    ) -> List[ActionItem]:
        """
        Check for fields that may need normalization and route to chat.

        These are fields where the value exists but interpretation is needed,
        such as owner salary normalization or management fee classification.
        """
        action_items: List[ActionItem] = []

        for field_name, field_config in CHAT_ROUTED_FIELDS.items():
            # Check if the base field exists and might need normalization
            base_field = field_name.replace("_normalization", "").replace("_adjustment", "")
            value = session_data.get(base_field) or session_data.get(field_name)

            if value is not None:
                # Check if normalization has already been addressed
                normalized_key = f"{base_field}_normalized"
                if session_data.get(normalized_key):
                    continue

                # Check if this is a field that typically needs review
                if self._needs_normalization_review(field_name, value, session_data):
                    action = ActionItem(
                        field=field_name,
                        field_label=field_config["label"],
                        reason=field_config["reason"],
                        interface=InterfaceRoute.CHAT,
                        priority=2,
                        current_value=value,
                        suggested_question=self._generate_normalization_question(
                            field_name, field_config["label"], value, session_data
                        ),
                    )
                    action_items.append(action)

        return action_items

    def _needs_normalization_review(
        self,
        field_name: str,
        value: Any,
        session_data: Dict[str, Any],
    ) -> bool:
        """
        Determine if a field value needs normalization review.

        Uses heuristics to detect potentially non-operational or abnormal values.
        """
        if field_name in ("owner_salary", "owner_salary_normalization"):
            # Check if owner salary seems unusual compared to industry benchmarks
            revenue = session_data.get("revenue", 0)
            if revenue and isinstance(revenue, (int, float, Decimal)):
                # Flag if owner salary is more than 15% of revenue (unusual for most businesses)
                if value and isinstance(value, (int, float, Decimal)):
                    if float(value) / float(revenue) > 0.15:
                        return True

        if field_name == "management_fee":
            # Management fees should always be reviewed for arm's length
            return True

        if field_name in ("non_operational_costs", "exceptional_items", "personal_expenses"):
            # These always need classification
            return value is not None and value != 0

        return False

    def _generate_normalization_question(
        self,
        field_name: str,
        label: str,
        value: Any,
        session_data: Dict[str, Any],
    ) -> Optional[str]:
        """
        DEPRECATED: Question generation moved to Titan (The Brain).

        BRAIN & MUSCLE ARCHITECTURE:
        ValuationIQ (The Muscle) returns triage flags, not questions.
        Titan's TriageService converts flags to questions via Claude.

        This method is kept for backward compatibility but returns None.
        Titan should handle question generation based on triage_flags.
        """
        # Return None - question generation is now handled by Titan
        return None

    def _determine_interface(self, field_name: str) -> InterfaceRoute:
        """
        DEPRECATED: Determine which interface should handle this field.

        BRAIN & MUSCLE ARCHITECTURE:
        Routing decisions are now made by Titan (The Brain), not ValuationIQ.
        This method is kept for backward compatibility but should not be used
        for making actual routing decisions.

        Titan's TriageService handles routing based on its own configuration.
        """
        # Return MANUAL as default - Titan will override with its own logic
        return InterfaceRoute.MANUAL

    def _generate_question(self, field_name: str, label: str) -> Optional[str]:
        """
        DEPRECATED: Question generation moved to Titan (The Brain).

        BRAIN & MUSCLE ARCHITECTURE:
        ValuationIQ (The Muscle) returns triage flags, not questions.
        Titan's TriageService converts flags to questions via Claude.

        This method is kept for backward compatibility but returns None.
        Titan should handle question generation based on triage_flags.
        """
        # Return None - question generation is now handled by Titan
        return None

    def _calculate_completeness_score(
        self,
        session_data: Dict[str, Any],
        required_fields: Dict[str, Dict[str, Any]],
        optional_fields: Dict[str, Dict[str, Any]],
    ) -> int:
        """
        Calculate overall completeness score (0-100).

        Required fields contribute more to the score than optional fields.
        """
        total_weight = 0.0
        achieved_weight = 0.0

        # Required fields (weight multiplied by 2 for importance)
        for field_name, config in required_fields.items():
            weight = config.get("weight", 1.0) * 2.0
            total_weight += weight

            value = session_data.get(field_name)
            if value is not None and value != "":
                achieved_weight += weight

        # Optional fields
        for field_name, config in optional_fields.items():
            weight = config.get("weight", 0.5)
            total_weight += weight

            value = session_data.get(field_name)
            if value is not None and value != "":
                achieved_weight += weight

        if total_weight == 0:
            return 0

        score = int((achieved_weight / total_weight) * 100)
        return min(100, max(0, score))

    def _is_ready_for_calculation(self, session_data: Dict[str, Any]) -> bool:
        """
        Check if minimum data requirements are met for calculation.

        Requires at minimum: company_name, industry, revenue, ebitda
        """
        minimum_fields = ["company_name", "industry", "revenue", "ebitda"]

        for field in minimum_fields:
            value = session_data.get(field)
            if value is None or value == "":
                return False

        return True

    def build_session_field_state(
        self,
        session_data: Dict[str, Any],
        field_sources: Optional[Dict[str, DataSource]] = None,
    ) -> SessionFieldState:
        """
        Build a complete SessionFieldState from session data.

        This creates the full state object that can be stored in the session
        and synced between Calculator and Chat interfaces.
        """
        # First, run gap analysis
        gap_analysis = self.analyze(
            session_data=session_data,
            field_sources=field_sources,
        )

        # Build field metadata
        field_metadata: Dict[str, FieldMetadata] = {}
        for field_name, value in session_data.items():
            if field_name not in field_metadata:
                source = DataSource.USER_INPUT
                if field_sources and field_name in field_sources:
                    source = field_sources[field_name]

                status = FieldStatus.AVAILABLE if value else FieldStatus.MISSING
                confidence = SOURCE_CONFIDENCE.get(source, 0.85)

                field_metadata[field_name] = FieldMetadata(
                    status=status,
                    source=source,
                    confidence=confidence,
                    original_value=value,
                    suggested_interface=self._determine_interface(field_name),
                    last_updated=datetime.utcnow(),
                )

        return SessionFieldState(
            data=session_data,
            field_metadata=field_metadata,
            gap_analysis=gap_analysis,
            sync_version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def update_field(
        self,
        state: SessionFieldState,
        field_name: str,
        value: Any,
        source: DataSource = DataSource.USER_INPUT,
        updated_by: Optional[str] = None,
    ) -> SessionFieldState:
        """
        Update a single field and recalculate gap analysis.

        This is used for real-time sync updates from both Chat and Calculator.

        Args:
            state: Current session field state
            field_name: Name of the field to update
            value: New value for the field
            source: Source of the update
            updated_by: User ID or 'system' for the update

        Returns:
            Updated SessionFieldState with new gap analysis
        """
        # Update the data
        state.data[field_name] = value

        # Update field metadata
        state.field_metadata[field_name] = FieldMetadata(
            status=FieldStatus.AVAILABLE if value else FieldStatus.MISSING,
            source=source,
            confidence=SOURCE_CONFIDENCE.get(source, 0.85),
            original_value=value,
            suggested_interface=self._determine_interface(field_name),
            last_updated=datetime.utcnow(),
            updated_by=updated_by,
        )

        # Recalculate gap analysis
        state.gap_analysis = self.analyze(
            session_data=state.data,
            field_sources={k: v.source for k, v in state.field_metadata.items()},
            existing_metadata=state.field_metadata,
        )

        # Increment sync version
        state.sync_version += 1
        state.updated_at = datetime.utcnow()

        return state
