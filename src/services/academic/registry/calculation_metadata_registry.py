"""
Calculation Metadata Registry

Loads and manages calculation metadata from YAML configuration.
Links calculations to academic sources and validation rules.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

import os
import threading
from typing import Dict, List, Optional

import yaml

from src.services.academic.models import CalculationMetadata, ConfidenceLevel
from src.services.academic.registry.academic_source_registry import get_source_registry
from src.services.academic.registry.confidence_level_parser import parse_confidence_level
from src.services.academic.validation_rules import VALIDATION_RULES_REGISTRY
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CalculationMetadataRegistry:
    """
    Registry for calculation metadata loaded from YAML configuration.

    Responsibilities:
    - Load calculation metadata from YAML file
    - Parse and validate metadata
    - Link calculations to academic sources
    - Link calculations to validation rules
    - Provide access methods for metadata retrieval

    Benefits:
    - Config-driven (easier to maintain)
    - Separation of data and code
    - Single source of truth
    - Easy to add new calculations without code changes
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize registry and load calculation metadata from YAML.

        Args:
            config_path: Path to calculation_metadata.yaml (defaults to config/)
        """
        self.logger = logger
        self._metadata: Dict[str, CalculationMetadata] = {}
        self._source_registry = get_source_registry()

        # Default to config directory relative to this file
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(
                os.path.dirname(current_dir), "config", "calculation_metadata.yaml"
            )

        self._load_metadata(config_path)

    def _load_metadata(self, config_path: str) -> None:
        """
        Load calculation metadata from YAML configuration file.

        Args:
            config_path: Path to YAML configuration file
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                metadata_list = yaml.safe_load(f)

            if not metadata_list:
                self.logger.warning(f"No calculation metadata found in {config_path}")
                return

            # Parse each calculation metadata
            for metadata_dict in metadata_list:
                try:
                    metadata = self._parse_metadata(metadata_dict)
                    self._metadata[metadata.calculation_id] = metadata
                except (ValueError, TypeError, AttributeError, KeyError) as e:
                    self.logger.error(
                        f"Failed to parse metadata for {metadata_dict.get('calculation_id', 'unknown')}: {e}",
                        exc_info=True,
                    )

            self.logger.info(
                f"Loaded {len(self._metadata)} calculation metadata entries from {config_path}"
            )

        except FileNotFoundError:
            self.logger.error(f"Calculation metadata config not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            self.logger.error(f"Failed to parse YAML config: {e}")
            raise

    def _parse_metadata(self, metadata_dict: dict) -> CalculationMetadata:
        """
        Parse metadata dictionary into CalculationMetadata object.

        Args:
            metadata_dict: Dictionary from YAML

        Returns:
            CalculationMetadata object
        """
        # Resolve academic sources by ID
        source_ids = metadata_dict.get("source_ids", [])
        academic_sources = []
        for source_id in source_ids:
            source = self._source_registry.get_source(source_id)
            if source:
                academic_sources.append(source)
            else:
                self.logger.warning(
                    f"Source '{source_id}' not found for calculation '{metadata_dict['calculation_id']}'"
                )

        # Resolve validation rules by ID
        validation_rule_ids = metadata_dict.get("validation_rule_ids", [])
        validation_rules = []
        for rule_id in validation_rule_ids:
            # Convert rule_id to uppercase attribute name (e.g., 'dcf_wacc_range' -> 'DCF_WACC_RANGE')
            rule_attr = rule_id.upper()
            if hasattr(VALIDATION_RULES_REGISTRY, rule_attr):
                rule = getattr(VALIDATION_RULES_REGISTRY, rule_attr)
                validation_rules.append(rule)
            else:
                self.logger.warning(
                    f"Validation rule '{rule_id}' not found for calculation '{metadata_dict['calculation_id']}'"
                )

        # Parse confidence level
        confidence_str = metadata_dict.get("confidence_level", "high")
        confidence_level = parse_confidence_level(confidence_str)

        return CalculationMetadata(
            calculation_id=metadata_dict["calculation_id"],
            calculation_name=metadata_dict["calculation_name"],
            description=metadata_dict["description"],
            academic_sources=academic_sources,
            validation_rules=validation_rules,
            formula=metadata_dict.get("formula"),
            formula_latex=metadata_dict.get("formula_latex"),
            confidence_level=confidence_level,
            category=metadata_dict.get("category"),
            notes=metadata_dict.get("notes"),
        )

    def get_metadata(self, calculation_id: str) -> Optional[CalculationMetadata]:
        """
        Get calculation metadata by ID.

        Args:
            calculation_id: Calculation identifier

        Returns:
            CalculationMetadata if found, None otherwise
        """
        return self._metadata.get(calculation_id)

    def get_all_metadata(self) -> List[CalculationMetadata]:
        """
        Get all calculation metadata.

        Returns:
            List of all CalculationMetadata objects
        """
        return list(self._metadata.values())

    def get_metadata_by_category(self, category: str) -> List[CalculationMetadata]:
        """
        Get all metadata for a specific category.

        Args:
            category: Category to filter by

        Returns:
            List of matching metadata
        """
        return [metadata for metadata in self._metadata.values() if metadata.category == category]

    def get_calculation_count(self) -> int:
        """Get total number of calculations loaded"""
        return len(self._metadata)

    def get_all_calculation_ids(self) -> List[str]:
        """Get list of all calculation IDs"""
        return list(self._metadata.keys())

    def calculation_exists(self, calculation_id: str) -> bool:
        """Check if calculation exists in registry"""
        return calculation_id in self._metadata

    def get_sme_calculations(self) -> List[CalculationMetadata]:
        """
        Get all SME-specific calculations.

        Returns:
            List of SME-specific metadata
        """
        return [
            metadata
            for metadata in self._metadata.values()
            if metadata.category and "sme" in metadata.category
        ]

    def get_categories(self) -> List[str]:
        """
        Get list of all unique categories.

        Returns:
            List of category names
        """
        categories = set()
        for metadata in self._metadata.values():
            if metadata.category:
                categories.add(metadata.category)
        return sorted(list(categories))

    def get_summary(self) -> Dict[str, any]:
        """
        Get summary of loaded calculation metadata.

        Returns:
            Dictionary with metadata statistics
        """
        category_counts = {}
        for metadata in self._metadata.values():
            if metadata.category:
                category_counts[metadata.category] = category_counts.get(metadata.category, 0) + 1

        confidence_counts = {}
        for metadata in self._metadata.values():
            conf_name = metadata.confidence_level.value
            confidence_counts[conf_name] = confidence_counts.get(conf_name, 0) + 1

        # Count calculations with formulas
        with_formula = sum(1 for m in self._metadata.values() if m.formula)
        with_latex = sum(1 for m in self._metadata.values() if m.formula_latex)

        return {
            "total_calculations": len(self._metadata),
            "calculations_by_category": category_counts,
            "calculations_by_confidence": confidence_counts,
            "sme_calculations_count": len(self.get_sme_calculations()),
            "with_formula": with_formula,
            "with_latex_formula": with_latex,
            "categories": self.get_categories(),
        }


# Create global singleton instance
_registry_instance: Optional[CalculationMetadataRegistry] = None
_registry_lock = threading.Lock()


def get_metadata_registry() -> CalculationMetadataRegistry:
    """
    Get or create singleton instance of CalculationMetadataRegistry.
    Thread-safe via double-checked locking.

    Returns:
        Singleton CalculationMetadataRegistry instance
    """
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = CalculationMetadataRegistry()
    return _registry_instance
