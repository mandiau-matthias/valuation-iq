"""
Content Block Parser

Parses rendered HTML into semantic blocks for intelligent pagination.

Uses BeautifulSoup4 to identify element types, extract HTML fragments,
and apply height heuristics for pagination calculations.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from bs4 import BeautifulSoup, Tag

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ContentBlock:
    """
    Represents a semantic content block for pagination.

    Attributes:
        type: Semantic type of the block
        html: Raw HTML content
        estimated_height: Estimated height in points (pt)
        keep_with_next: If True, this block should stay with the next block
        page_break_before: If True, force a page break before this block
        is_orphan_protected: If True, prevent orphaning this block alone
        element_id: Optional ID for debugging
        section_id: Optional section ID for grouping blocks under same heading
    """

    type: Literal[
        "heading", "paragraph", "table", "callout", "hero_card", "list", "grid", "div", "page_break"
    ]
    html: str
    estimated_height: float
    keep_with_next: bool = False
    page_break_before: bool = False
    is_orphan_protected: bool = True
    element_id: Optional[str] = None
    section_id: Optional[str] = None  # New: groups blocks under same heading


class ContentBlockParser:
    """
    Parses HTML into semantic content blocks with height estimates.

    Uses calibrated heuristics to estimate the rendered height of each
    block for intelligent pagination.
    """

    def __init__(self, heuristics_path: Optional[Path] = None):
        """
        Initialize parser with calibration data.

        Args:
            heuristics_path: Path to pagination_heuristics.json
                           (defaults to config/pagination_heuristics.json)
        """
        if heuristics_path is None:
            # Try multiple paths for Docker and local environments
            possible_paths = [
                Path("/app/config/pagination_heuristics.json"),  # Docker container path
                Path(__file__).parent.parent.parent.parent.parent
                / "config"
                / "pagination_heuristics.json",  # Local dev
                Path.cwd() / "config" / "pagination_heuristics.json",  # Current working directory
            ]

            heuristics_path = None
            for path in possible_paths:
                if path.exists():
                    heuristics_path = path
                    break

            if heuristics_path is None:
                # Use inline fallback heuristics
                logger.warning(
                    "⚠️ [PAGINATION-PARSER] No calibration file found, using fallback heuristics",
                    extra={"searched_paths": [str(p) for p in possible_paths]},
                )
                self._use_fallback_heuristics()
                return

        # Load calibration data
        try:
            with open(heuristics_path, "r", encoding="utf-8") as f:
                self.calibration = json.load(f)
            self.heuristics = self.calibration["elements"]
            self.formulas = self.calibration.get("formulas", {})
            logger.info(
                "✅ [PAGINATION-PARSER] Loaded calibration data",
                extra={
                    "heuristics_count": len(self.heuristics),
                    "heuristics_path": str(heuristics_path),
                },
            )
        except Exception as e:
            logger.error(
                f"❌ [PAGINATION-PARSER] Failed to load calibration data: {e}", exc_info=True
            )
            self._use_fallback_heuristics()

    def _use_fallback_heuristics(self):
        """Use inline fallback heuristics when config file is not available."""
        self.heuristics = {
            "h1": 100.0,
            "h2": 64.0,
            "h3": 50.0,
            "paragraph_short": 35.0,
            "paragraph_medium": 50.0,
            "paragraph_long": 85.0,
            "table_single_row": 180.0,
            "table_five_rows": 320.0,
            "table_with_caption": 220.0,
            "table_row_incremental": 35.0,
            "table_caption_overhead": 40.0,
            "table_header_height": 45.0,
            "table_card_padding": 48.0,
            "table_base_height": 145.0,
            "report_callout": 80.0,
            "report_callout_warning": 80.0,
            "hero_card": 450.0,
            "grid_layout_2col": 180.0,
            "unordered_list": 90.0,
            "list_item": 30.0,
        }
        self.formulas = {
            "paragraph_height_per_line": 19.2,
            "table_row_height": 35.0,
            "average_chars_per_line": 90,
            "char_width_pt": 5.67,
        }
        self.calibration = {
            "metadata": {
                "method": "fallback",
                "a4_content_height_pt": 728.5,
                "safe_content_height_pt": 692.07,
            },
            "elements": self.heuristics,
            "formulas": self.formulas,
        }
        logger.info(
            "✅ [PAGINATION-PARSER] Using fallback heuristics",
            extra={"heuristics_count": len(self.heuristics)},
        )

    def parse(self, html: str, skip_static_sections: bool = True) -> List[ContentBlock]:
        """
        Parse HTML into content blocks.

        Unwraps existing <div class="page"> containers and re-parses content
        for intelligent re-pagination. Preserves static sections (cover, TOC).

        Args:
            html: Rendered HTML string (from Jinja2)
            skip_static_sections: If True, skip cover page and TOC (they have manual page breaks)

        Returns:
            List of ContentBlock objects with height estimates
        """
        # DEPLOYMENT VERIFICATION MARKER
        logger.info(
            "[PAGINATION-PARSER] Content block parser initialized",
            extra={
                "parser_version": "2.0.0-selective-grouping",
                "fix_deployed": "Unwraps divs to preserve semantic heading types",
            },
        )

        soup = BeautifulSoup(html, "html.parser")
        blocks = []

        logger.info("[PAGINATION-PARSER] Starting HTML parsing (unwrapping existing page divs)")

        report_div = self._report_container(soup)
        previous_was_heading = False

        for element in report_div.find_all(recursive=False):
            previous_was_heading = self._parse_top_level_element(
                element,
                blocks,
                skip_static_sections=skip_static_sections,
                previous_was_heading=previous_was_heading,
            )

        logger.info(
            f"✅ [PAGINATION-PARSER] Parsed {len(blocks)} content blocks from dynamic sections",
            extra={"block_count": len(blocks)},
        )

        return blocks

    def _report_container(self, soup: BeautifulSoup) -> Tag:
        report_div = soup.find("div", class_="final-report")
        if report_div:
            return report_div
        logger.warning("[PAGINATION-PARSER] No .final-report div found, parsing entire document")
        return soup

    def _parse_top_level_element(
        self,
        element: Tag,
        blocks: List[ContentBlock],
        *,
        skip_static_sections: bool,
        previous_was_heading: bool,
    ) -> bool:
        if self._should_skip_top_level_element(element, skip_static_sections):
            return False

        if element.name == "div" and "page" in element.get("class", []):
            logger.debug(
                "[PAGINATION-PARSER] Unwrapping content from existing page div",
                extra={"page_has_children": len(list(element.children))},
            )
            self._parse_page_content(element, blocks)
            return False

        if element.name == "div":
            return self._parse_generic_div_children(element, blocks, previous_was_heading)

        block = self._parse_element(element)
        return self._append_block_with_heading_context(block, blocks, previous_was_heading)

    def _should_skip_top_level_element(self, element: Tag, skip_static_sections: bool) -> bool:
        if skip_static_sections and self._is_static_section(element):
            logger.debug(f"[PAGINATION-PARSER] Skipping static section: {element.get('class', [])}")
            return True
        return "page-break" in element.get("class", [])

    def _parse_generic_div_children(
        self,
        element: Tag,
        blocks: List[ContentBlock],
        previous_was_heading: bool,
    ) -> bool:
        logger.debug(
            "[PAGINATION-PARSER] Unwrapping generic div to extract semantic blocks",
            extra={"div_has_children": len(list(element.children))},
        )
        for child in element.find_all(recursive=False):
            block = self._parse_element(child)
            previous_was_heading = self._append_block_with_heading_context(
                block, blocks, previous_was_heading
            )
        return previous_was_heading

    def _append_block_with_heading_context(
        self,
        block: Optional[ContentBlock],
        blocks: List[ContentBlock],
        previous_was_heading: bool,
    ) -> bool:
        if not block:
            return previous_was_heading

        if previous_was_heading and block.type in ["table", "callout", "hero_card"]:
            logger.debug(
                f"[PAGINATION-PARSER] ✨ Binding {block.type} to previous heading (Designer rule)"
            )
        blocks.append(block)
        return block.type == "heading"

    def _parse_page_content(self, page_element: Tag, blocks: List[ContentBlock]):
        """
        Recursively parse content within a page div.

        Extracts all semantic blocks (headings, paragraphs, tables, etc.)
        from within an existing page container for re-pagination.

        CRITICAL: Enforces semantic cohesion - all content under a heading gets the same section_id.

        Args:
            page_element: The <div class="page"> element
            blocks: List to append parsed blocks to
        """
        current_section_id = None  # Track current section for grouping

        # Parse all direct children of the page
        for child in page_element.find_all(recursive=False):
            # Skip page breaks inside pages
            if "page-break" in child.get("class", []):
                # Convert to explicit page_break block
                blocks.append(
                    ContentBlock(
                        type="page_break",
                        html="",
                        estimated_height=0.0,
                        page_break_before=True,
                    )
                )
                current_section_id = None
                continue

            # CRITICAL FIX: Handle ALL divs by recursing into children
            # Divs are just containers - we need to unwrap them to preserve semantic heading types
            if child.name == "div":
                # Recurse into div children to extract semantic blocks (headings, tables, etc.)
                for section_child in child.find_all(recursive=False):
                    block = self._parse_element(section_child)
                    if block:
                        # Start new section on headings
                        if block.type == "heading":
                            current_section_id = block.element_id or f"section_{len(blocks)}"
                            block.section_id = current_section_id
                            # FORCE LOG VISIBILITY
                            logger.error(
                                f"🚨 [PARSER] HEADING BLOCK CREATED: type=heading, section_id={current_section_id}, html={block.html[:100]}"
                            )
                        elif current_section_id:
                            block.section_id = current_section_id
                            logger.debug(
                                f"[PAGINATION-PARSER] ✨ Adding {block.type} to section {current_section_id}"
                            )

                        blocks.append(block)
            else:
                # Parse as normal block (non-div elements)
                block = self._parse_element(child)
                if block:
                    # DESIGNER FIX: Group all content under same heading
                    if block.type == "heading":
                        current_section_id = block.element_id or f"section_{len(blocks)}"
                        block.section_id = current_section_id
                        logger.debug(
                            f"[PAGINATION-PARSER] 📑 Starting new section: {current_section_id}"
                        )
                    elif current_section_id:
                        block.section_id = current_section_id
                        logger.debug(
                            f"[PAGINATION-PARSER] ✨ Adding {block.type} to section {current_section_id}"
                        )

                    blocks.append(block)

    def _is_static_section(self, element: Tag) -> bool:
        """
        Check if element is a static section (cover page, TOC) that should not be paginated.

        Args:
            element: BeautifulSoup Tag element

        Returns:
            True if this is a static section to skip
        """
        if not isinstance(element, Tag):
            return False

        # Check for cover page/sheet classes
        classes = element.get("class", [])
        if any(cls in ["cover-page", "cover-sheet"] for cls in classes):
            return True

        # Check for cover page by style attribute (page: cover)
        style = element.get("style", "")
        if "page: cover" in style or "page:cover" in style:
            return True

        # Check if this is the TOC page by looking for TOC-specific content
        # TOC typically has h1 with "Table of Contents" or similar
        if element.name == "div" and "page" in classes:
            toc_heading = element.find("h1")
            if toc_heading:
                text = toc_heading.get_text(strip=True).lower()
                if "table of contents" in text or "contents" in text:
                    return True

        return False

    def _is_page_break(self, element: Tag) -> bool:
        return "page-break" in element.get("class", [])

    def _is_heading(self, element: Tag) -> bool:
        return element.name in ["h1", "h2", "h3"]

    def _is_table(self, element: Tag) -> bool:
        return (
            element.name == "table"
            or element.name == "div"
            and "table-card" in element.get("class", [])
        )

    def _is_report_callout(self, element: Tag) -> bool:
        return element.name == "div" and "report-callout" in element.get("class", [])

    def _is_hero_card(self, element: Tag) -> bool:
        if element.name != "div" or "upswitch-navy" not in element.get("style", ""):
            return False
        return "padding: 48pt 40pt" in element.get("style", "")

    def _is_grid_layout(self, element: Tag) -> bool:
        return element.name == "div" and "grid-layout" in element.get("class", [])

    def _is_paragraph(self, element: Tag) -> bool:
        return element.name == "p"

    def _is_list(self, element: Tag) -> bool:
        return element.name in ["ul", "ol"]

    def _page_break_block(self, element: Tag) -> ContentBlock:
        return ContentBlock(
            type="page_break",
            html=str(element),
            estimated_height=0.0,
            page_break_before=True,
        )

    def _parse_element(self, element: Tag) -> Optional[ContentBlock]:
        """Parse a single HTML element into a ContentBlock."""
        if not isinstance(element, Tag):
            return None

        # Handle explicit page breaks
        if "page-break" in element.get("class", []):
            return self._page_break_block(element)

        # Handle headings
        if self._is_heading(element):
            return self._parse_heading(element)

        # Handle tables (with or without .table-card wrapper)
        if self._is_table(element):
            return self._parse_table(element)

        # Handle report callouts
        if self._is_report_callout(element):
            return self._parse_callout(element)

        # Handle hero cards (navy background cards from valuation_conclusion.html)
        if self._is_hero_card(element):
            return self._parse_hero_card(element)

        # Handle grid layouts
        if self._is_grid_layout(element):
            return self._parse_grid(element)

        # Handle paragraphs
        if self._is_paragraph(element):
            return self._parse_paragraph(element)

        # Handle lists
        if self._is_list(element):
            return self._parse_list(element)

        # Handle generic divs (report-section, etc.)
        if element.name == "div":
            # CRITICAL FIX: Don't wrap children in a div block!
            # Divs are just containers - let children be parsed separately
            # so headings maintain their semantic type for pagination rules.
            # Return None here - the parent parse() method will process children.
            return None

        return None

    def _parse_heading(self, element: Tag) -> ContentBlock:
        """Parse heading element."""
        level = element.name  # 'h1', 'h2', 'h3'
        height = self.heuristics.get(level, 60.0)

        return ContentBlock(
            type="heading",
            html=str(element),
            estimated_height=height,
            keep_with_next=True,  # Headings stick to next element
            element_id=element.get("id"),
        )

    def _parse_paragraph(self, element: Tag) -> ContentBlock:
        """Parse paragraph element."""
        text = element.get_text(strip=True)
        text_length = len(text)

        # Estimate height based on text length
        if text_length < 100:
            height = self.heuristics.get("paragraph_short", 35.0)
        elif text_length < 300:
            height = self.heuristics.get("paragraph_medium", 50.0)
        else:
            height = self.heuristics.get("paragraph_long", 85.0)

        return ContentBlock(
            type="paragraph",
            html=str(element),
            estimated_height=height,
        )

    def _parse_table(self, element: Tag) -> ContentBlock:
        """Parse table element (with or without .table-card wrapper)."""
        # Find actual table element
        table = element if element.name == "table" else element.find("table")

        if not table:
            return ContentBlock(
                type="table",
                html=str(element),
                estimated_height=self.heuristics.get("table_single_row", 180.0),
            )

        # Count rows
        tbody = table.find("tbody")
        rows = len(tbody.find_all("tr", recursive=False)) if tbody else 0

        # Check for caption
        has_caption = table.find("caption") is not None

        # Calculate height
        base_height = self.heuristics.get("table_base_height", 145.0)
        row_height = self.heuristics.get("table_row_incremental", 35.0)
        caption_overhead = self.heuristics.get("table_caption_overhead", 40.0) if has_caption else 0
        card_padding = self.heuristics.get("table_card_padding", 48.0)

        total_height = base_height + (rows * row_height) + caption_overhead + card_padding

        return ContentBlock(
            type="table",
            html=str(element),
            estimated_height=total_height,
            is_orphan_protected=True,  # Tables should not be orphaned
        )

    def _parse_callout(self, element: Tag) -> ContentBlock:
        """Parse report callout element."""
        # Check if it's a warning callout
        is_warning = "warning" in element.get("class", [])

        height = self.heuristics.get(
            "report_callout_warning" if is_warning else "report_callout", 80.0
        )

        return ContentBlock(
            type="callout",
            html=str(element),
            estimated_height=height,
        )

    def _parse_hero_card(self, element: Tag) -> ContentBlock:
        """Parse hero card (large navy card with valuation summary)."""
        height = self.heuristics.get("hero_card", 450.0)

        return ContentBlock(
            type="hero_card",
            html=str(element),
            estimated_height=height,
            is_orphan_protected=True,  # Hero cards should not be split
        )

    def _parse_grid(self, element: Tag) -> ContentBlock:
        """Parse grid layout."""
        height = self.heuristics.get("grid_layout_2col", 180.0)

        return ContentBlock(
            type="grid",
            html=str(element),
            estimated_height=height,
        )

    def _parse_list(self, element: Tag) -> ContentBlock:
        """Parse list element (ul/ol)."""
        # Count list items
        items = element.find_all("li", recursive=False)
        item_count = len(items)

        item_height = self.heuristics.get("list_item", 30.0)
        total_height = item_count * item_height

        return ContentBlock(
            type="list",
            html=str(element),
            estimated_height=total_height,
        )
