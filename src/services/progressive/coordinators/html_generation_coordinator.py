"""
HTML Generation Coordinator

BANK-GRADE: SRP-Compliant wrapper around ProgressiveHTMLGenerator

REFACTORED: This coordinator now delegates to ProgressiveHTMLGenerator for actual
HTML generation, maintaining Single Responsibility Principle.

RESPONSIBILITY: Coordinate HTML generation (delegate to generator)
DOES NOT: Generate HTML directly (delegated to ProgressiveHTMLGenerator)

BACKWARD COMPATIBILITY: Maintains same public API while using new generator internally
"""

import logging
from collections.abc import Mapping
from typing import Optional, cast

from ..progressive_html_generator import ProgressiveHTMLGenerator

logger = logging.getLogger(__name__)


class HTMLGenerationCoordinator:
    """
    SRP-COMPLIANT: Coordinates HTML generation by delegating to ProgressiveHTMLGenerator.

    REFACTORED: Extracted actual HTML generation to ProgressiveHTMLGenerator.
    This coordinator now has a single responsibility: coordinate HTML generation.

    SINGLE RESPONSIBILITY: Coordination (not generation)
    """

    def __init__(
        self,
        html_generator: Optional[ProgressiveHTMLGenerator] = None,
    ) -> None:
        """
        Initialize the HTML generation coordinator.

        SRP: Delegates HTML generation to dedicated generator class

        Args:
            html_generator: Optional ProgressiveHTMLGenerator instance (injected for testing)
        """
        self.logger = logger
        # SRP: Delegate HTML generation to dedicated class
        self.html_generator = html_generator or ProgressiveHTMLGenerator()

    def generate_welcome_html(self, data: Mapping[str, object]) -> str:
        """
        Generate welcome HTML for instant preview.

        SRP: Delegates to ProgressiveHTMLGenerator

        Args:
            data: Dictionary containing company data

        Returns:
            HTML string with welcome message
        """
        company_name = data.get("company_name", "Your Business")
        return cast(str, self.html_generator.generate_welcome_html(company_name))

    def generate_progress_html(self, collected: int, total: int) -> str:
        """
        Generate progress tracker HTML.

        SRP: Delegates to ProgressiveHTMLGenerator

        Args:
            collected: Number of fields collected
            total: Total number of fields

        Returns:
            HTML string with progress tracker
        """
        return cast(str, self.html_generator.generate_progress_html(collected, total))

    def generate_placeholder_range(self, data: Mapping[str, object]) -> str:
        """
        Generate placeholder valuation range.

        SRP: Delegates to ProgressiveHTMLGenerator

        Args:
            data: Dictionary containing revenue data

        Returns:
            Placeholder valuation range string
        """
        return cast(str, self.html_generator.generate_placeholder_range(dict(data)))

    def generate_next_steps(self, data: Mapping[str, object]) -> list[str]:
        """
        Generate next steps based on missing data.

        SRP: Delegates to ProgressiveHTMLGenerator

        Args:
            data: Dictionary containing collected data

        Returns:
            List of next steps (max 3)
        """
        return cast(list[str], self.html_generator.generate_next_steps(dict(data)))
