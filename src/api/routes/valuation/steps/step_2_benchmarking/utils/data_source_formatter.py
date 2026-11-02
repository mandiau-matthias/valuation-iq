"""
Data Source Formatter

Formats technical data source codes into professional, user-friendly descriptions
for display in valuation reports. Aligns with academic sources and SME valuation best practices.

Author: Upswitch Valuation Engine Team
Date: December 2025
"""

from typing import Any, Dict, List, Optional


class DataSourceFormatter:
    """
    Formats data sources for professional display in reports.

    Maps technical source codes (e.g., "business_type_db") to professional
    descriptions (e.g., "Business-type-specific SME multiples from regional market data")
    and includes appropriate academic source citations.
    """

    UPSWITCH_INDEX_CONTRACT_DISPLAY = "Upswitch Index benchmark contract"
    UPSWITCH_INDEX_CONTRACT_SOURCES = frozenset(
        {
            "delphi_benchmark_contract",
            "delphi_resolved_benchmark",
            "titan_enrichment",
            "upswitch_index_benchmark_contract",
        }
    )

    # Mapping of technical source codes to professional display names
    SOURCE_DISPLAY_MAP = {
        "DELPHI_BENCHMARK_CONTRACT": UPSWITCH_INDEX_CONTRACT_DISPLAY,
        "delphi_benchmark_contract": UPSWITCH_INDEX_CONTRACT_DISPLAY,
        "delphi-resolved-benchmark": UPSWITCH_INDEX_CONTRACT_DISPLAY,
        "titan_enrichment": UPSWITCH_INDEX_CONTRACT_DISPLAY,
        "upswitch_index_benchmark_contract": UPSWITCH_INDEX_CONTRACT_DISPLAY,
        "business_type_db": "Disclosed legacy business-type cache fallback",
        "fmp_api": "Disclosed fallback public-company market data",
        "cache": "Disclosed fallback cached market data",
        "fallback_business_type_defaults": "Disclosed fallback business-type defaults",
        "fallback_business_category_defaults": "Disclosed fallback category defaults",
        "fallback_industry_defaults": "Disclosed fallback industry defaults",
        "fallback_generic_defaults": "Disclosed generic fallback",
        "business_type_default": "Disclosed fallback business-type defaults",
        "business_category_default": "Disclosed fallback category defaults",
        "industry_rules": "Industry-specific business rules",
        "hardcoded_industry": "Disclosed hardcoded industry fallback",
        "hardcoded_default": "Disclosed emergency generic fallback",
        "unknown": "Benchmark unavailable",
        "forced_fallback": "Explicit fallback multiples",
        "fallback_recovery": "Recovery fallback multiples",
        "fallback_defaults": "Explicit default fallback multiples",
    }

    # Academic sources associated with each data source type
    ACADEMIC_SOURCES_MAP = {
        "titan_enrichment": [
            {
                "author": "Upswitch Index",
                "year": 2026,
                "title": UPSWITCH_INDEX_CONTRACT_DISPLAY,
                "type": "published_benchmark_contract",
            },
        ],
        "business_type_db": [
            {
                "author": "Upswitch Index",
                "year": 2026,
                "title": "Legacy Business-Type Cache",
                "type": "internal_cache",
            },
        ],
        "fmp_api": [
            {
                "author": "Financial Modeling Prep",
                "year": 2026,
                "title": "Public-company market data fallback",
                "type": "disclosed_external_fallback",
            },
        ],
        "cache": [
            {
                "author": "Upswitch",
                "year": 2026,
                "title": "Cached disclosed fallback data",
                "type": "disclosed_external_fallback",
            },
        ],
        "fallback_business_type_defaults": [
            {
                "author": "Upswitch",
                "year": 2026,
                "title": "Explicit fallback defaults",
                "type": "disclosed_default_fallback",
            },
        ],
        "fallback_business_category_defaults": [
            {
                "author": "Upswitch",
                "year": 2026,
                "title": "Explicit fallback defaults",
                "type": "disclosed_default_fallback",
            },
        ],
        "fallback_industry_defaults": [
            {
                "author": "Upswitch",
                "year": 2026,
                "title": "Explicit fallback defaults",
                "type": "disclosed_default_fallback",
            },
        ],
    }

    @staticmethod
    def format_data_source_display(
        data_source: str, data_source_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format technical data source code into professional display description.

        Args:
            data_source: Technical source code (e.g., "business_type_db")
            data_source_details: Optional dictionary with additional source details

        Returns:
            Professional display description
        """
        if not data_source:
            return "Estimated multiples"

        display_name = DataSourceFormatter._display_name(data_source)
        decorated = DataSourceFormatter._decorated_display_name(
            data_source,
            display_name,
            data_source_details,
        )
        if decorated:
            return decorated

        return display_name

    @staticmethod
    def _display_name(data_source: str) -> str:
        if DataSourceFormatter.is_upswitch_index_contract_source(data_source):
            return DataSourceFormatter.UPSWITCH_INDEX_CONTRACT_DISPLAY
        return DataSourceFormatter.SOURCE_DISPLAY_MAP.get(
            data_source, data_source.replace("_", " ").title()
        )

    @staticmethod
    def is_upswitch_index_contract_source(data_source: object) -> bool:
        normalized = str(data_source or "").strip().lower().replace("-", "_")
        return normalized in DataSourceFormatter.UPSWITCH_INDEX_CONTRACT_SOURCES or (
            "delphi" in normalized and "benchmark" in normalized and "contract" in normalized
        )

    @staticmethod
    def _decorated_display_name(
        data_source: str,
        display_name: str,
        data_source_details: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if DataSourceFormatter.is_upswitch_index_contract_source(data_source):
            return DataSourceFormatter._titan_contract_display_name(
                display_name, data_source_details
            )
        if data_source == "business_type_db":
            return DataSourceFormatter._business_type_display_name(
                display_name, data_source_details
            )
        if data_source == "fmp_api":
            return f"{display_name} (calibrated for SME size)"
        return None

    @staticmethod
    def _titan_contract_display_name(
        display_name: str,
        data_source_details: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if not data_source_details:
            return None
        contract = data_source_details.get("benchmark_provenance") or data_source_details.get(
            "benchmark_contract"
        )
        if not isinstance(contract, dict):
            return None
        tier = contract.get("tier")
        country = contract.get("country_code")
        if tier and country:
            return f"{display_name} ({country}, tier {tier})"
        return None

    @staticmethod
    def _business_type_display_name(
        display_name: str,
        data_source_details: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if not data_source_details:
            return None
        business_type_id = data_source_details.get("business_type_id")
        return f"{display_name} ({business_type_id})" if business_type_id else None

    @staticmethod
    def get_academic_sources_for_data_source(
        data_source: str,
    ) -> List[Dict[str, Any]]:
        """
        Get academic sources associated with a data source.

        Args:
            data_source: Technical source code

        Returns:
            List of academic source dictionaries
        """
        source_key = (
            "titan_enrichment"
            if DataSourceFormatter.is_upswitch_index_contract_source(data_source)
            else data_source
        )
        return DataSourceFormatter.ACADEMIC_SOURCES_MAP.get(source_key, [])

    @staticmethod
    def generate_source_explanation(
        data_source: str,
        business_type_id: Optional[str] = None,
        data_source_details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate detailed explanation of data source for reports.

        Args:
            data_source: Technical source code
            business_type_id: Optional business type identifier
            data_source_details: Optional dictionary with additional source details

        Returns:
            Detailed explanation string suitable for reports
        """
        display_name = DataSourceFormatter.format_data_source_display(
            data_source, data_source_details
        )

        # Generate explanation based on source type
        if data_source == "business_type_db":
            explanation = f"{display_name} were selected from the legacy business-type cache. "
            if business_type_id:
                explanation += (
                    f"Multiples are calibrated specifically for business type '{business_type_id}' "
                    f"to reflect the unique risk profile and characteristics of this business type. "
                )
            explanation += (
                "A concrete local valuation should prefer the resolved benchmark contract "
                "when available."
            )
            return explanation
        elif DataSourceFormatter.is_upswitch_index_contract_source(data_source):
            contract = (data_source_details or {}).get("benchmark_provenance") or (
                data_source_details or {}
            ).get("benchmark_contract")
            if isinstance(contract, dict):
                return (
                    f"{display_name} supplies the calculation multiple and the report "
                    "explanation from one published benchmark contract "
                    f"(benchmark_id={contract.get('benchmark_id')}, "
                    f"dataset_version_id={contract.get('dataset_version_id')})."
                )
            return f"{display_name} supplies both calculation and explanation multiples."

        elif data_source == "fmp_api":
            explanation = (
                f"{display_name} were derived from public company comparables "
                "and are not local private-SME evidence. They are only usable when "
                "the caller explicitly accepts a disclosed fallback, and must not "
                "be presented as a benchmark contract."
            )
            return explanation

        elif data_source == "cache":
            explanation = (
                f"{display_name} were retrieved from cached market data. This is "
                "a disclosed fallback lane only, not local evidence and not a "
                "published benchmark contract."
            )
            return explanation

        elif data_source.startswith("fallback"):
            explanation = (
                f"{display_name} were used only because explicit fallback consent "
                "was present. These values are not defensible local evidence and "
                "must not be described as resolved benchmark multiples."
            )
            return explanation

        else:
            return f"{display_name} were used for this valuation."

    @staticmethod
    def format_academic_citations(data_source: str) -> str:
        """
        Format academic source citations for a data source.

        Args:
            data_source: Technical source code

        Returns:
            Formatted citation string (e.g., "VFB Belgium 2024, Vlerick 2023")
        """
        sources = DataSourceFormatter.get_academic_sources_for_data_source(data_source)

        if not sources:
            return ""

        citations = []
        for source in sources:
            author = source.get("author", "")
            year = source.get("year", "")
            if author and year:
                citations.append(f"{author} {year}")

        return ", ".join(citations) if citations else ""

    @staticmethod
    def get_source_confidence_level(data_source: str) -> str:
        """
        Get confidence level indicator for a data source.

        Args:
            data_source: Technical source code

        Returns:
            Confidence level: "very_high", "high", "medium", or "low"
        """
        confidence_map = {
            "titan_enrichment": "very_high",
            "business_type_db": "low",
            "fmp_api": "low",
            "cache": "low",
            "fallback_business_type_defaults": "low",
            "fallback_business_category_defaults": "low",
            "fallback_industry_defaults": "low",
            "fallback_generic_defaults": "low",
            "unknown": "low",
            "forced_fallback": "low",
        }

        return confidence_map.get(data_source, "medium")
