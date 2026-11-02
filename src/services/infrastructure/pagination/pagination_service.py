"""
Pagination Service

Orchestrates the smart pagination pipeline:
1. Load calibration data
2. Parse HTML into content blocks
3. Estimate heights
4. Run smart pagination
5. Render final paginated HTML
6. Validate page counts and content integrity

Main entry point for the pagination system.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from src.utils.logging import get_logger

from .content_block_parser import ContentBlockParser
from .page_renderer import PageRenderer
from .smart_paginator import Page, SmartPaginator

logger = get_logger(__name__)


class PaginationService:
    """
    Orchestrates the smart pagination pipeline.

    Takes unpaginated HTML (from Jinja2 templates) and returns properly
    paginated HTML with content flowed into A4 page containers.

    BANK-GRADE: Includes pagination provenance for debugging and audit trails.
    """

    def __init__(
        self,
        heuristics_path: Optional[Path] = None,
        max_page_height: Optional[float] = None,
        enable_validation: bool = True,
        track_provenance: bool = True,
    ):
        """
        Initialize pagination service.

        Args:
            heuristics_path: Path to pagination_heuristics.json
            max_page_height: Override max page height (defaults to safe A4 height)
            enable_validation: Enable content integrity validation
            track_provenance: Track pagination decisions for debugging (default: True)
        """
        self.parser = ContentBlockParser(heuristics_path=heuristics_path)
        self.paginator = (
            SmartPaginator(max_page_height=max_page_height) if max_page_height else SmartPaginator()
        )
        self.renderer = PageRenderer(preserve_metadata=True)
        self.enable_validation = enable_validation
        self.track_provenance = track_provenance
        self.last_provenance_data: Optional[Dict[str, Any]] = None

        logger.info(
            "✅ [PAGINATION-SERVICE] Initialized",
            extra={
                "max_page_height": self.paginator.max_page_height,
                "enable_validation": enable_validation,
                "track_provenance": track_provenance,
            },
        )

    async def paginate(self, html: str, preserve_static_sections: bool = True) -> str:
        """
        Main pagination pipeline with selective pagination.

        Args:
            html: Unpaginated HTML from Jinja2 template rendering
            preserve_static_sections: If True, preserve cover page and TOC as-is (default: True)

        Returns:
            Paginated HTML with dynamic content flowed into page containers,
            static sections (cover, TOC) preserved
        """
        start_time = time.time()

        logger.info(
            "Starting pagination",
            extra={
                "input_html_length": len(html),
                "preserve_static_sections": preserve_static_sections,
                "pagination_version": "2.1.3-robust-empty-grid-fix",
                "changes": "Made empty container detection more robust - checks for 'grid-layout' in HTML OR div/container type",
            },
        )

        try:
            # Extract static sections first (cover page, TOC)
            static_html = ""
            if preserve_static_sections:
                static_html = self._extract_static_sections(html)

            # Step 1: Parse HTML into content blocks (skip static sections)
            logger.info(
                "[PAGINATION-SERVICE] Step 1/4: Parsing dynamic content",
                extra={"preserve_static": preserve_static_sections},
            )
            blocks = self.parser.parse(html, skip_static_sections=preserve_static_sections)

            if not blocks:
                logger.warning("[PAGINATION-SERVICE] No blocks parsed, returning original HTML")
                return html

            logger.info(
                "[PAGINATION-SERVICE] Parsed content blocks", extra={"block_count": len(blocks)}
            )

            # Step 2: Run smart pagination with selective section grouping
            logger.info(
                "[PAGINATION-SERVICE] Step 2/4: Applying smart pagination rules",
                extra={"total_blocks": len(blocks)},
            )
            pages = self.paginator.paginate(blocks)

            if not pages:
                logger.warning("[PAGINATION-SERVICE] No pages generated, returning original HTML")
                return html

            # FORCE LOG VISIBILITY
            logger.error(
                f"🚨 [PAGINATION-SERVICE] Smart pagination complete: {len(pages)} pages",
                extra={"pages_generated": len(pages)},
            )

            # Step 3: Render paginated HTML (combine static + dynamic)
            logger.info(
                "[PAGINATION-SERVICE] Step 3/4: Rendering paginated HTML",
                extra={"page_count": len(pages), "has_static_content": bool(static_html)},
            )
            if preserve_static_sections and static_html:
                # Combine static sections + paginated dynamic content
                paginated_content = self.renderer.render_simple(pages)  # Just the page containers
                paginated_html = self._combine_static_and_dynamic(
                    html, static_html, paginated_content
                )
            else:
                # Full document rendering
                paginated_html = self.renderer.render(pages, original_html=html)

            # Step 4: Validate if enabled
            if self.enable_validation:
                logger.info("[PAGINATION-SERVICE] Step 4/4: Validating pagination")
                validation_result = self._validate_pagination(html, paginated_html, pages)

                if not validation_result["valid"]:
                    logger.warning(
                        "⚠️ [PAGINATION-SERVICE] Validation warnings", extra=validation_result
                    )

            elapsed_ms = (time.time() - start_time) * 1000

            # BANK-GRADE: Capture pagination provenance for debugging
            if self.track_provenance:
                self.last_provenance_data = self._capture_pagination_provenance(
                    blocks=blocks,
                    pages=pages,
                    validation_result=validation_result if self.enable_validation else None,
                    processing_time_ms=elapsed_ms,
                )

            logger.info(
                "[PAGINATION-SERVICE] Pagination complete with selective section grouping",
                extra={
                    "page_count": len(pages),
                    "input_size": len(html),
                    "output_size": len(paginated_html),
                    "processing_time_ms": elapsed_ms,
                    "provenance_tracked": self.track_provenance,
                },
            )

            return paginated_html

        except Exception as e:
            logger.error(
                "[PAGINATION-SERVICE] Pagination failed, returning original HTML",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "fallback_action": "returning_original_html",
                },
                exc_info=True,
            )

            # Return original HTML on error
            return html

    def _validate_pagination(
        self, original_html: str, paginated_html: str, pages: List
    ) -> Dict[str, Any]:
        """
        Validate pagination results.

        Args:
            original_html: Original unpaginated HTML
            paginated_html: Paginated HTML
            pages: List of Page objects

        Returns:
            Validation result dictionary
        """
        validation = {
            "valid": True,
            "warnings": [],
            "stats": {
                "original_length": len(original_html),
                "paginated_length": len(paginated_html),
                "page_count": len(pages),
                "avg_page_height": (
                    sum(p.current_height for p in pages) / len(pages) if pages else 0
                ),
                "max_page_height": max(p.current_height for p in pages) if pages else 0,
            },
        }

        # Check for significant size differences (shouldn't lose content)
        size_ratio = len(paginated_html) / len(original_html) if len(original_html) > 0 else 0
        if size_ratio < 0.9 or size_ratio > 1.2:
            validation["valid"] = False
            validation["warnings"].append(
                f"Significant size difference: {size_ratio:.2%} of original"
            )

        # Check for overflow pages
        for page in pages:
            if page.current_height > self.paginator.max_page_height * 1.05:  # 5% tolerance
                validation["warnings"].append(
                    f"Page {page.number} exceeds max height: {page.current_height:.2f}pt > {self.paginator.max_page_height:.2f}pt"
                )

        # Check for very short pages (possible pagination issues)
        for page in pages:
            if page.current_height < 100 and page.number != len(pages):  # Not last page
                validation["warnings"].append(
                    f"Page {page.number} is very short: {page.current_height:.2f}pt"
                )

        return validation

    def _extract_static_sections(self, html: str) -> str:
        """
        Extract static sections (cover page, TOC) from HTML.

        Args:
            html: Original HTML

        Returns:
            HTML string containing only static sections
        """
        soup = BeautifulSoup(html, "html.parser")
        static_elements = []

        # Find final-report container
        report_div = soup.find("div", class_="final-report")
        if not report_div:
            return ""

        found_toc = False
        for element in report_div.find_all(recursive=False):
            if self._is_cover_static_section(element):
                static_elements.append(str(element))
                continue

            if self._is_toc_static_section(element):
                static_elements.append(str(element))
                found_toc = True
                continue

            if found_toc and self._is_page_break(element):
                # Extract this ONE page break, then stop
                static_elements.append(str(element))
                break  # Stop extracting after first page break following TOC

        return "\n".join(static_elements)

    def _is_cover_static_section(self, element: Tag) -> bool:
        classes = element.get("class", [])
        style = element.get("style", "")

        if any(cls in ["cover-page", "cover-sheet"] for cls in classes):
            return True
        return "page: cover" in style or "page:cover" in style

    def _is_toc_static_section(self, element: Tag) -> bool:
        classes = element.get("class", [])
        if element.name != "div" or "page" not in classes:
            return False

        toc_heading = element.find("h1")
        if not toc_heading:
            return False

        text = toc_heading.get_text(strip=True).lower()
        return "table of contents" in text or "contents" in text

    def _is_page_break(self, element: Tag) -> bool:
        return "page-break" in element.get("class", [])

    def _combine_static_and_dynamic(
        self, original_html: str, static_html: str, dynamic_html: str
    ) -> str:
        """
        Combine static sections with paginated dynamic content.

        Args:
            original_html: Original HTML (for extracting head/metadata)
            static_html: Static sections (cover, TOC)
            dynamic_html: Paginated dynamic content

        Returns:
            Combined HTML document
        """
        soup = BeautifulSoup(original_html, "html.parser")

        # Extract head section
        head = soup.find("head")
        head_html = str(head) if head else ""

        # Build final HTML
        html_parts = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            head_html,
            "<body>",
            '<div class="final-report">',
            static_html,  # Cover page + TOC
            dynamic_html,  # Paginated content sections
            "</div>",
            "</body>",
            "</html>",
        ]

        return "\n".join(html_parts)

    def _capture_pagination_provenance(
        self,
        blocks: List,
        pages: List,
        validation_result: Optional[Dict[str, Any]],
        processing_time_ms: float,
    ) -> Dict[str, Any]:
        """
        BANK-GRADE: Capture pagination provenance for debugging and audit trails.

        Records pagination decisions including:
        - Total blocks and pages created
        - Page break locations and reasons
        - Overflow handling decisions
        - Validation results
        - Performance metrics

        Args:
            blocks: List of ContentBlock objects that were paginated
            pages: List of Page objects created
            validation_result: Optional validation results
            processing_time_ms: Time taken to paginate

        Returns:
            Dictionary with pagination provenance metadata
        """
        provenance = {
            "timestamp": time.time(),
            "input_stats": {
                "total_blocks": len(blocks),
                "block_types": {},
            },
            "output_stats": {
                "total_pages": len(pages),
                "avg_page_height": (
                    sum(p.current_height for p in pages) / len(pages) if pages else 0
                ),
                "max_page_height": max(p.current_height for p in pages) if pages else 0,
                "min_page_height": min(p.current_height for p in pages) if pages else 0,
            },
            "page_breaks": [],
            "pagination_rules_applied": [],
            "validation": validation_result,
            "performance": {
                "processing_time_ms": processing_time_ms,
                "blocks_per_ms": len(blocks) / processing_time_ms if processing_time_ms > 0 else 0,
            },
        }

        # Analyze block types
        for block in blocks:
            block_type = block.type
            provenance["input_stats"]["block_types"][block_type] = (
                provenance["input_stats"]["block_types"].get(block_type, 0) + 1
            )

        # Analyze page breaks and overflow decisions
        for i, page in enumerate(pages):
            if i == 0:
                continue  # First page doesn't have a break

            # Determine why this page started
            first_block = page.blocks[0] if page.blocks else None
            if first_block:
                break_reason = self._determine_break_reason(first_block, i)
                provenance["page_breaks"].append(
                    {
                        "page_number": page.number,
                        "first_block_type": first_block.type,
                        "first_block_section": (
                            first_block.section_id if hasattr(first_block, "section_id") else None
                        ),
                        "page_height": page.current_height,
                        "break_reason": break_reason,
                    }
                )

        return provenance

    def _determine_break_reason(self, first_block, page_number: int) -> str:
        """
        Determine why a page break occurred at this location.

        Args:
            first_block: First block on the page
            page_number: Page number

        Returns:
            String describing the reason for the page break
        """
        if hasattr(first_block, "page_break_before") and first_block.page_break_before:
            return "explicit_page_break"
        elif first_block.type == "heading":
            return "heading_overflow_rule"
        elif first_block.type == "table":
            return "table_integrity_rule"
        elif hasattr(first_block, "preserve_together") and first_block.preserve_together:
            return "orphan_prevention_rule"
        else:
            return "natural_overflow"

    def get_last_provenance(self) -> Optional[Dict[str, Any]]:
        """
        Get pagination provenance from last pagination operation.

        BANK-GRADE: Enables debugging and audit trails for pagination decisions.

        Returns:
            Dictionary with pagination provenance metadata, or None if not tracked
        """
        return self.last_provenance_data
