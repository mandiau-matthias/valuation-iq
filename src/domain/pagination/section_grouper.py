"""
Section Grouper Domain Service

Groups content blocks into sections based on headings.
Pure domain logic with zero infrastructure dependencies.

Business Rule:
    All content blocks following a heading belong to that heading's section
    until the next heading is encountered.

Academic Reference:
    Domain-Driven Design (Eric Evans) - Domain Services
    Services that don't naturally belong to an entity or value object.
"""

from typing import List, Optional
from dataclasses import replace

from .value_objects import SectionId
from src.services.infrastructure.pagination.content_block_parser import ContentBlock

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SectionGrouper:
    """
    Domain service for grouping content blocks into sections.
    
    Applies business rule:
        - Headings start new sections
        - All following blocks belong to that section
        - Section continues until next heading
    
    This is pure domain logic - no parsing, no infrastructure.
    """
    
    def group_by_section(self, blocks: List[ContentBlock]) -> List[ContentBlock]:
        """
        Group content blocks into sections by assigning section_id.
        
        Business Logic:
            1. When encountering a heading, start new section
            2. Assign section ID to heading and all following blocks
            3. Continue until next heading
            4. Blocks before first heading have no section_id
        
        Args:
            blocks: List of ContentBlock objects (from parser)
        
        Returns:
            List of ContentBlock objects with section_id assigned
        
        Example:
            Input:
                [Paragraph, Heading('intro'), Paragraph, Table, Heading('data'), Paragraph]
            
            Output:
                [Paragraph(section_id=None),
                 Heading(section_id='intro'),
                 Paragraph(section_id='intro'),
                 Table(section_id='intro'),
                 Heading(section_id='data'),
                 Paragraph(section_id='data')]
        """
        if not blocks:
            return []
        
        logger.info(
            "🔍 [SECTION-GROUPER] Grouping blocks into sections",
            extra={"total_blocks": len(blocks)}
        )
        
        current_section: Optional[SectionId] = None
        section_count = 0
        grouped_blocks: List[ContentBlock] = []
        
        for i, block in enumerate(blocks):
            # Start new section on heading
            if block.type == 'heading':
                # Generate section ID from element_id or sequential number
                section_id_value = block.element_id or f"section_{section_count}"
                current_section = SectionId(section_id_value)
                section_count += 1
                
                logger.debug(
                    f"[SECTION-GROUPER] 📑 New section: {current_section}",
                    extra={
                        "block_index": i,
                        "section_id": str(current_section),
                        "element_id": block.element_id,
                    }
                )
            
            # Assign current section to block (may be None for blocks before first heading)
            if current_section is not None:
                # Create new block with section_id assigned
                updated_block = replace(block, section_id=str(current_section))
                grouped_blocks.append(updated_block)
                
                logger.debug(
                    f"[SECTION-GROUPER] ✨ Assigned {block.type} to section {current_section}",
                    extra={
                        "block_index": i,
                        "block_type": block.type,
                        "section_id": str(current_section),
                    }
                )
            else:
                # Block before first heading - no section
                grouped_blocks.append(block)
                
                logger.debug(
                    f"[SECTION-GROUPER] Block {i} before first heading (no section)",
                    extra={"block_index": i, "block_type": block.type}
                )
        
        sections_created = section_count
        blocks_with_sections = sum(1 for b in grouped_blocks if b.section_id is not None)
        
        logger.info(
            "✅ [SECTION-GROUPER] Section grouping complete",
            extra={
                "total_blocks": len(grouped_blocks),
                "sections_created": sections_created,
                "blocks_with_sections": blocks_with_sections,
                "blocks_without_sections": len(grouped_blocks) - blocks_with_sections,
            }
        )
        
        return grouped_blocks
    
    def get_section_blocks(
        self,
        blocks: List[ContentBlock],
        section_id: SectionId
    ) -> List[ContentBlock]:
        """
        Get all blocks belonging to a specific section.
        
        Args:
            blocks: List of all content blocks
            section_id: Section ID to filter by
        
        Returns:
            List of blocks in that section (including heading)
        """
        return [
            block for block in blocks
            if block.section_id == str(section_id)
        ]
    
    def get_section_headings(self, blocks: List[ContentBlock]) -> List[ContentBlock]:
        """
        Get all heading blocks (section starters).
        
        Args:
            blocks: List of all content blocks
        
        Returns:
            List of heading blocks
        """
        return [block for block in blocks if block.type == 'heading']
    
    def validate_section_structure(self, blocks: List[ContentBlock]) -> bool:
        """
        Validate that section structure is correct.
        
        Business Rules:
            - Every section has exactly one heading (the first block)
            - Section ID matches across all blocks in section
        
        Args:
            blocks: List of content blocks with section_id assigned
        
        Returns:
            True if structure is valid, False otherwise
        """
        sections = {}
        
        for block in blocks:
            if block.section_id is None:
                continue
            
            if block.section_id not in sections:
                sections[block.section_id] = []
            
            sections[block.section_id].append(block)
        
        # Validate each section
        for section_id, section_blocks in sections.items():
            # Check: First block must be heading
            if section_blocks and section_blocks[0].type != 'heading':
                logger.warning(
                    f"⚠️ [SECTION-GROUPER] Section {section_id} does not start with heading",
                    extra={
                        "section_id": section_id,
                        "first_block_type": section_blocks[0].type,
                    }
                )
                return False
            
            # Check: Only one heading per section
            heading_count = sum(1 for b in section_blocks if b.type == 'heading')
            if heading_count > 1:
                logger.warning(
                    f"⚠️ [SECTION-GROUPER] Section {section_id} has {heading_count} headings (expected 1)",
                    extra={"section_id": section_id, "heading_count": heading_count}
                )
                return False
        
        return True






