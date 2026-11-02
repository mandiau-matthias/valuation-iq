"""
Academic Source Registry

Loads and manages academic sources from YAML configuration.
Provides clean separation between data and code.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

import os
from typing import Dict, List, Optional

import yaml

from src.services.academic.models import AcademicSource, ConfidenceLevel, SourceType
from src.services.academic.registry.confidence_level_parser import parse_confidence_level
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AcademicSourceRegistry:
    """
    Registry for academic sources loaded from YAML configuration.

    Responsibilities:
    - Load sources from YAML file
    - Parse and validate source data
    - Provide access methods for source retrieval
    - Maintain source index by ID

    Benefits:
    - Config-driven (easier to maintain)
    - Separation of data and code
    - Single source of truth
    - Easy to add new sources without code changes
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize registry and load sources from YAML.

        Args:
            config_path: Path to academic_sources.yaml (defaults to config/academic_sources.yaml)
        """
        self.logger = logger
        self._sources: Dict[str, AcademicSource] = {}

        # Default to config directory relative to this file
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(
                os.path.dirname(current_dir), "config", "academic_sources.yaml"
            )

        self._load_sources(config_path)

    def _load_sources(self, config_path: str) -> None:
        """
        Load academic sources from YAML configuration file.

        Args:
            config_path: Path to YAML configuration file
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                sources_data = yaml.safe_load(f)

            if not sources_data:
                self.logger.warning(f"No sources found in {config_path}")
                return

            # Parse each source
            for source_dict in sources_data:
                try:
                    source = self._parse_source(source_dict)
                    self._sources[source.source_id] = source
                except (ValueError, TypeError, AttributeError, KeyError) as e:
                    self.logger.error(
                        f"Failed to parse source {source_dict.get('source_id', 'unknown')}: {e}",
                        exc_info=True,
                    )

            self.logger.info(f"Loaded {len(self._sources)} academic sources from {config_path}")

        except FileNotFoundError:
            self.logger.error(f"Academic sources config not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            self.logger.error(f"Failed to parse YAML config: {e}")
            raise

    def _parse_source(self, source_dict: dict) -> AcademicSource:
        """
        Parse source dictionary into AcademicSource object.

        Args:
            source_dict: Dictionary from YAML

        Returns:
            AcademicSource object
        """
        # Map string source_type to enum
        source_type_str = source_dict.get("source_type", "academic_textbook")
        source_type = self._parse_source_type(source_type_str)

        # Map string confidence_level to enum
        confidence_str = source_dict.get("confidence_level", "high")
        confidence_level = parse_confidence_level(confidence_str)

        return AcademicSource(
            source_id=source_dict["source_id"],
            author=source_dict["author"],
            year=source_dict["year"],
            title=source_dict["title"],
            source_type=source_type,
            publisher=source_dict.get("publisher"),
            journal=source_dict.get("journal"),
            volume=source_dict.get("volume"),
            issue=source_dict.get("issue"),
            pages=source_dict.get("pages"),
            edition=source_dict.get("edition"),
            relevance=source_dict["relevance"],
            confidence_level=confidence_level,
            verified=source_dict.get("verified", False),
            notes=source_dict.get("notes"),
        )

    def _parse_source_type(self, type_str: str) -> SourceType:
        """Convert string source type to enum"""
        type_map = {
            "academic_textbook": SourceType.ACADEMIC_TEXTBOOK,
            "peer_reviewed_journal": SourceType.PEER_REVIEWED_JOURNAL,
            "big_4_methodology": SourceType.BIG_4_METHODOLOGY,
            "industry_report": SourceType.INDUSTRY_REPORT,
            "professional_standard": SourceType.PROFESSIONAL_STANDARD,
            "academic_research": SourceType.ACADEMIC_RESEARCH,
        }
        return type_map.get(type_str, SourceType.ACADEMIC_TEXTBOOK)

    def get_source(self, source_id: str) -> Optional[AcademicSource]:
        """
        Get academic source by ID.

        Args:
            source_id: Source identifier

        Returns:
            AcademicSource if found, None otherwise
        """
        return self._sources.get(source_id)

    def get_all_sources(self) -> List[AcademicSource]:
        """
        Get all academic sources.

        Returns:
            List of all AcademicSource objects
        """
        return list(self._sources.values())

    def get_sources_by_type(self, source_type: SourceType) -> List[AcademicSource]:
        """
        Get all sources of a specific type.

        Args:
            source_type: Type of source to filter by

        Returns:
            List of matching sources
        """
        return [source for source in self._sources.values() if source.source_type == source_type]

    def get_source_count(self) -> int:
        """Get total number of sources loaded"""
        return len(self._sources)

    def get_sme_sources(self) -> List[AcademicSource]:
        """
        Get all SME-specific sources.

        Returns:
            List of SME-specific sources
        """
        sme_source_ids = [
            "trugman_2017",
            "hitchner_2017",
            "damodaran_2011",
            "coulon_2021",
            "west_2012",
            "abor_2016",
            "koeplin_2000",
            "officer_2007",
            "emory_2002",
            "astrachan_2003",
            "petersen_2004",
            "pepperdine_2024",
            "bizcomps_2024",
            "done_deals_2024",
            "vfb_belgium_2024",
            "vlerick_2023",
            "uclouvain_2022",
            "european_commission_2023",
        ]
        return [self._sources[sid] for sid in sme_source_ids if sid in self._sources]

    def get_belgian_sources(self) -> List[AcademicSource]:
        """
        Get all Belgian/European-specific sources.

        Returns:
            List of Belgian/European sources
        """
        belgian_source_ids = [
            "vfb_belgium_2024",
            "vlerick_2023",
            "uclouvain_2022",
            "coulon_2021",
            "done_deals_2024",
            "european_commission_2023",
        ]
        return [self._sources[sid] for sid in belgian_source_ids if sid in self._sources]

    def source_exists(self, source_id: str) -> bool:
        """Check if source exists in registry"""
        return source_id in self._sources

    def get_sources_by_year_range(self, start_year: int, end_year: int) -> List[AcademicSource]:
        """
        Get sources published within a year range.

        Args:
            start_year: Starting year (inclusive)
            end_year: Ending year (inclusive)

        Returns:
            List of sources in year range
        """
        return [
            source for source in self._sources.values() if start_year <= source.year <= end_year
        ]

    def get_verified_sources(self) -> List[AcademicSource]:
        """Get all verified sources"""
        return [source for source in self._sources.values() if source.verified]

    def get_summary(self) -> Dict[str, any]:
        """
        Get summary of loaded sources.

        Returns:
            Dictionary with source statistics
        """
        type_counts = {}
        for source in self._sources.values():
            type_name = source.source_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        confidence_counts = {}
        for source in self._sources.values():
            conf_name = source.confidence_level.value
            confidence_counts[conf_name] = confidence_counts.get(conf_name, 0) + 1

        return {
            "total_sources": len(self._sources),
            "sources_by_type": type_counts,
            "sources_by_confidence": confidence_counts,
            "verified_count": len(self.get_verified_sources()),
            "sme_sources_count": len(self.get_sme_sources()),
            "belgian_sources_count": len(self.get_belgian_sources()),
        }


import threading

_registry_instance: Optional[AcademicSourceRegistry] = None
_registry_lock = threading.Lock()


def get_source_registry() -> AcademicSourceRegistry:
    """
    Get or create singleton instance of AcademicSourceRegistry.
    Thread-safe via double-checked locking.
    """
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = AcademicSourceRegistry()
    return _registry_instance
