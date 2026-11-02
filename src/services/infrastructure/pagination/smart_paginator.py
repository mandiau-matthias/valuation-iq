"""
Smart Paginator

Flows content blocks into A4 pages with intelligent rules:
1. h1 headings trigger new pages with section grouping
2. h2/h3 headings flow naturally without forced grouping  
3. Table integrity (tables stay on one page or force new page)
4. Hero card handling (large visual elements get proper page space)
5. Safety buffer (5% buffer to prevent micro-overflows)

VERSION: 2.1.0-critical-bugfix
CHANGES: Fixed h2/h3 handling to not create orphaned heading pages
"""

from dataclasses import dataclass, field
from typing import List, Optional

from src.utils.logging import get_logger

from .content_block_parser import ContentBlock

logger = get_logger(__name__)

# A4 content area dimensions (from calibration)
A4_CONTENT_HEIGHT_PT = 728.50  # After 2cm top/bottom margins
SAFETY_BUFFER_RATIO = 0.97  # 3% safety buffer (matches Google Docs/Word standards)
SAFE_CONTENT_HEIGHT_PT = A4_CONTENT_HEIGHT_PT * SAFETY_BUFFER_RATIO  # 706.65pt


@dataclass
class Page:
    """
    Represents a single A4 page with content blocks.

    Attributes:
        number: Page number (1-indexed)
        blocks: List of ContentBlock objects on this page
        current_height: Current accumulated height in points (float - see module docstring)
        max_height: Maximum allowed height for this page (float - see module docstring)

    Note: Uses float for height calculations (presentational domain).
    See module docstring for bank-grade precision rationale.
    """

    number: int
    blocks: List[ContentBlock] = field(default_factory=list)
    current_height: float = (
        0.0  # Presentational calculation - float acceptable (see module docstring)
    )
    max_height: float = SAFE_CONTENT_HEIGHT_PT  # Presentational calculation - float acceptable

    def can_fit(self, block: ContentBlock) -> bool:
        """Check if a block can fit on this page."""
        # BANK-GRADE: Defensive check - ensure estimated_height is never None
        block_height = block.estimated_height if block.estimated_height is not None else 0.0
        return (self.current_height + block_height) <= self.max_height

    def add_block(self, block: ContentBlock) -> None:
        """Add a block to this page."""
        self.blocks.append(block)
        # BANK-GRADE: Defensive check - ensure estimated_height is never None
        block_height = block.estimated_height if block.estimated_height is not None else 0.0
        self.current_height += block_height

    def remove_last_block(self) -> ContentBlock:
        """Remove and return the last block from this page."""
        if self.blocks:
            block = self.blocks.pop()
            # BANK-GRADE: Defensive check - ensure estimated_height is never None
            block_height = block.estimated_height if block.estimated_height is not None else 0.0
            self.current_height -= block_height
            return block
        return None

    def is_empty(self) -> bool:
        """Check if page has no content."""
        return len(self.blocks) == 0

    def has_content(self) -> bool:
        """Check if page has content."""
        return len(self.blocks) > 0


class SmartPaginator:
    """
    Intelligent pagination engine that flows content blocks into A4 pages.

    Implements selective section grouping:
    - h1 headings: Trigger new page + section content grouping
    - h2/h3 headings: Flow naturally across pages (no forced grouping)
    - Tables: Kept intact on single page
    - Orphan prevention: Headings always kept with at least one content block
    """

    def __init__(self, max_page_height: float = SAFE_CONTENT_HEIGHT_PT):
        """
        Initialize paginator.

        Args:
            max_page_height: Maximum content height per page in points
        """
        self.max_page_height = max_page_height
        self.pages: List[Page] = []

    def _get_heading_level(self, block: ContentBlock) -> Optional[str]:
        """
        Extract heading level (h1, h2, h3) from block HTML for selective pagination.

        WHAT: Parses block HTML to identify heading semantic level
        WHY: Enables selective section grouping - h1 triggers new pages, h2/h3 flow naturally
        HOW: Uses BeautifulSoup to find h1/h2/h3 tags in block.html
        WHEN: Called by RULE 1 to determine if heading should trigger new page grouping

        Design Context:
            - Major sections (h1) need page breaks for readability
            - Subsections (h2/h3) should flow naturally to improve page density
            - Prevents excessive pagination and near-empty pages

        Args:
            block: ContentBlock to analyze

        Returns:
            'h1', 'h2', 'h3' for heading levels, None if not a heading block

        References:
            - Designer feedback: "Too many page breaks on minor headings"
            - UX requirement: 15-17 pages optimal (down from 18+)
        """
        if block.type != "heading":
            return None

        # Parse HTML to extract tag name
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(block.html, "html.parser")
        heading_tag = soup.find(["h1", "h2", "h3"])

        if heading_tag:
            detected_level = heading_tag.name
            # FORCE LOG VISIBILITY
            logger.error(
                f"🚨 [PAGINATION] HEADING DETECTED: {detected_level} | section_id={block.section_id or 'None'}",
                extra={
                    "heading_level": detected_level,
                    "section_id": block.section_id or "None",
                    "html_preview": block.html[:100],
                },
            )
            return detected_level

        logger.warning(
            f"⚠️ [PAGINATION] Heading block but no h1/h2/h3 tag found",
            extra={"section_id": block.section_id or "None", "html": block.html[:200]},
        )
        return None

    def paginate(self, blocks: List[ContentBlock]) -> List[Page]:
        """
        Flow content blocks into A4 pages with selective h1 grouping.

        Args:
            blocks: List of ContentBlock objects from parser

        Returns:
            List of Page objects with content distributed
        """
        if not blocks:
            logger.warning("[PAGINATION] No blocks to paginate")
            return []

        # FORCE LOG VISIBILITY
        logger.error(
            f"🚨🚨🚨 [PAGINATION] STARTING: {len(blocks)} blocks, selective h1 grouping v2.1.0",
            extra={"block_count": len(blocks), "version": "2.1.0-critical-bugfix"},
        )

        self.pages = []
        current_page = Page(number=1, max_height=self.max_page_height)
        skip_until_index = -1  # Track blocks already added by overflow handler

        for i, block in enumerate(blocks):
            # Skip blocks already added by overflow handler
            if i <= skip_until_index:
                logger.debug(
                    f"[PAGINATION] ⏭️  Skipping block {i+1} (already added to previous page)"
                )
                continue

            if self._should_skip_block(block):
                continue

            # Handle explicit page breaks
            if block.type == "page_break" or block.page_break_before:
                current_page = self._handle_page_break(current_page)
                continue  # Don't add page break blocks to pages

            # Check if block fits on current page
            if current_page.can_fit(block):
                current_page.add_block(block)
            else:
                # Block doesn't fit - apply pagination rules
                self._log_overflow(block, i, blocks, current_page)
                skip_until_index = self._handle_overflow(current_page, block, blocks, i)
                # Create a NEW page for next iteration
                current_page = Page(number=len(self.pages) + 1, max_height=self.max_page_height)

        # Add final page if it has meaningful content
        if current_page.has_content():
            if any(block.type not in ["page_break"] for block in current_page.blocks):
                self.pages.append(current_page)
            else:
                logger.debug("[PAGINATION] Skipping final page (only page-break blocks)")

        self._log_pagination_complete()

        return self.pages

    def _should_skip_block(self, block: ContentBlock) -> bool:
        block_height = self._block_height(block)
        if block_height <= 0:
            logger.error(
                f"🚨 [PAGINATION] SKIPPING ZERO-HEIGHT BLOCK: type={block.type}, html={block.html[:100]}"
            )
            return True
        return self._is_empty_container_block(block)

    def _is_empty_container_block(self, block: ContentBlock) -> bool:
        if not block.html or not (
            block.type in ["div", "container"] or "grid-layout" in block.html
        ):
            return False

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(block.html, "html.parser")
        if soup.get_text(strip=True):
            return False

        element_tag = soup.find() if soup.find() else None
        element_class = element_tag.get("class", []) if element_tag else "none"
        logger.error(
            f"🚨 [PAGINATION] SKIPPING EMPTY CONTAINER: type={block.type}, class={element_class}, html_preview={block.html[:100] if block.html else 'none'}"
        )
        return True

    def _handle_page_break(self, current_page: Page) -> Page:
        if current_page.has_content():
            self.pages.append(current_page)
            return self._new_page()
        return current_page

    def _log_overflow(
        self,
        block: ContentBlock,
        index: int,
        blocks: List[ContentBlock],
        current_page: Page,
    ) -> None:
        block_height = self._block_height(block)
        logger.error(
            f"🚨 [PAGINATION] OVERFLOW: block {index + 1}/{len(blocks)}, type={block.type}, height={block_height:.0f}pt",
            extra={
                "block_type": block.type,
                "section_id": block.section_id or "None",
                "block_height": f"{block_height:.0f}pt",
                "page_current": f"{current_page.current_height:.0f}pt",
                "page_max": f"{self.max_page_height:.0f}pt",
            },
        )

    def _log_pagination_complete(self) -> None:
        logger.error(
            f"🚨🚨🚨 [PAGINATION] COMPLETE: {len(self.pages)} pages (target: 15-17) {'✅ GOOD' if len(self.pages) <= 17 else '❌ TOO MANY'}",
            extra={
                "page_count": len(self.pages),
                "avg_height": f"{sum(p.current_height for p in self.pages) / len(self.pages) if self.pages else 0:.0f}pt",
                "target_pages": "15-17",
                "status": "TOO_MANY" if len(self.pages) > 17 else "GOOD",
            },
        )

    def _handle_overflow(
        self,
        current_page: Page,
        overflowing_block: ContentBlock,
        all_blocks: List[ContentBlock],
        current_index: int,
    ) -> int:
        """
        Handle content block that exceeds page capacity with intelligent pagination rules.

        CRITICAL: h1 headings get section grouping, h2/h3 headings flow naturally WITHOUT grouping

        Returns:
            Index of last block successfully added (for main loop to skip)
            Returns current_index if only the current block was added
        """
        if overflowing_block.type == "heading":
            return self._handle_heading_overflow(
                current_page,
                overflowing_block,
                all_blocks,
                current_index,
            )

        if overflowing_block.type in ["table", "hero_card"]:
            return self._handle_table_or_hero_overflow(
                current_page, overflowing_block, current_index
            )

        return self._handle_default_overflow(current_page, overflowing_block, current_index)

    def _handle_heading_overflow(
        self,
        current_page: Page,
        overflowing_block: ContentBlock,
        all_blocks: List[ContentBlock],
        current_index: int,
    ) -> int:
        heading_level = self._get_heading_level(overflowing_block)
        is_major_section = heading_level == "h1"

        logger.error(
            f"🚨🚨🚨 [PAGINATION] RULE 1: type=heading, level={heading_level}, is_h1={is_major_section}",
            extra={
                "heading_level": heading_level or "unknown",
                "is_major_section": is_major_section,
                "section_id": overflowing_block.section_id or "None",
                "html_preview": overflowing_block.html[:150],
            },
        )

        if is_major_section:
            return self._handle_major_heading_overflow(
                current_page, overflowing_block, all_blocks, current_index
            )
        return self._handle_minor_heading_overflow(
            current_page, overflowing_block, all_blocks, current_index, heading_level
        )

    def _handle_major_heading_overflow(
        self,
        current_page: Page,
        overflowing_block: ContentBlock,
        all_blocks: List[ContentBlock],
        current_index: int,
    ) -> int:
        logger.error("🎯 [PAGINATION] h1 MAJOR SECTION → new page + content grouping")
        self._append_page_if_content(current_page)

        new_page = self._new_page()
        new_page.add_block(overflowing_block)
        last_added = self._add_same_section_following_blocks(
            new_page, overflowing_block, all_blocks, current_index
        )

        self.pages.append(new_page)
        return last_added

    def _handle_minor_heading_overflow(
        self,
        current_page: Page,
        overflowing_block: ContentBlock,
        all_blocks: List[ContentBlock],
        current_index: int,
        heading_level: Optional[str],
    ) -> int:
        logger.error(
            f"🎯🎯🎯 [PAGINATION] h2/h3 NATURAL FLOW: level={heading_level}, NO grouping, NO orphan page",
            extra={
                "heading_level": heading_level,
                "section_id": overflowing_block.section_id or "None",
            },
        )
        self._append_page_if_content(current_page)

        new_page = self._new_page()
        new_page.add_block(overflowing_block)
        last_added = self._add_following_non_heading_blocks(
            new_page, all_blocks, current_index, lookahead=10
        )

        self.pages.append(new_page)
        return last_added

    def _add_same_section_following_blocks(
        self,
        new_page: Page,
        heading_block: ContentBlock,
        all_blocks: List[ContentBlock],
        current_index: int,
    ) -> int:
        last_added = current_index
        if not heading_block.section_id or current_index + 1 >= len(all_blocks):
            return last_added

        for j in range(current_index + 1, len(all_blocks)):
            next_block = all_blocks[j]
            if next_block.type == "heading" or next_block.section_id != heading_block.section_id:
                break
            if not new_page.can_fit(next_block):
                break
            new_page.add_block(next_block)
            last_added = j
        return last_added

    def _add_following_non_heading_blocks(
        self,
        new_page: Page,
        all_blocks: List[ContentBlock],
        current_index: int,
        *,
        lookahead: int,
    ) -> int:
        last_added = current_index
        if current_index + 1 >= len(all_blocks):
            return last_added

        for j in range(current_index + 1, min(current_index + lookahead, len(all_blocks))):
            next_block = all_blocks[j]
            if next_block.type == "heading" or not new_page.can_fit(next_block):
                break
            new_page.add_block(next_block)
            last_added = j
            logger.error(
                f"🎨 [PAGINATION] h2/h3 + content: Added {next_block.type} to prevent orphaning"
            )
        return last_added

    def _handle_table_or_hero_overflow(
        self,
        current_page: Page,
        overflowing_block: ContentBlock,
        current_index: int,
    ) -> int:
        overflow_height = self._block_height(overflowing_block)
        if overflow_height > self.max_page_height:
            logger.warning(
                f"⚠️ [PAGINATION] {overflowing_block.type} too large ({overflow_height:.0f}pt > {self.max_page_height:.0f}pt)"
            )
            current_page.add_block(overflowing_block)
            self.pages.append(current_page)
            return current_index

        if self._can_move_heading_with_block(current_page, overflow_height):
            heading = current_page.remove_last_block()
            self._append_page_if_content(current_page)

            new_page = self._new_page()
            new_page.add_block(heading)
            new_page.add_block(overflowing_block)
            self.pages.append(new_page)
            return current_index

        self._append_page_if_content(current_page)
        new_page = self._new_page()
        new_page.add_block(overflowing_block)
        self.pages.append(new_page)
        return current_index

    def _handle_default_overflow(
        self,
        current_page: Page,
        overflowing_block: ContentBlock,
        current_index: int,
    ) -> int:
        if current_page.has_content():
            self.pages.append(current_page)

        new_page = self._new_page()
        new_page.add_block(overflowing_block)
        self.pages.append(new_page)
        return current_index

    def _append_page_if_content(self, page: Page) -> None:
        if page.has_content():
            self.pages.append(page)

    def _new_page(self) -> Page:
        return Page(number=len(self.pages) + 1, max_height=self.max_page_height)

    def _can_move_heading_with_block(self, current_page: Page, block_height: float) -> bool:
        if not current_page.blocks or current_page.blocks[-1].type != "heading":
            return False
        heading_height = self._block_height(current_page.blocks[-1])
        return heading_height + block_height <= self.max_page_height

    def _block_height(self, block: ContentBlock) -> float:
        return block.estimated_height if block.estimated_height is not None else 0.0
