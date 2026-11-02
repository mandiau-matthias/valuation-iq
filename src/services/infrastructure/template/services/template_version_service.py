"""
Template Version Service

BANK-GRADE: Single Responsibility - Track template versions

RESPONSIBILITY:
- Calculate template file hashes
- Track template versions
- Generate version metadata
- Detect template changes

DOES NOT:
- Configure environment (delegated to TemplateConfigurationService)
- Transform data (delegated to TemplateDataTransformer)
- Render templates (delegated to TemplateRenderingService)
- Generate PDFs (delegated to PDFGenerationCoordinator)

SRP Compliance: This service has ONE reason to change - version tracking requirements
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class TemplateVersionService:
    """
    BANK-GRADE SRP-COMPLIANT: Tracks template versions for reproducibility.

    SINGLE RESPONSIBILITY: Template version tracking

    This service focuses solely on version management:
    - Calculating file hashes (SHA-256)
    - Tracking file sizes
    - Recording modification times
    - Generating version metadata

    Design Pattern: Service Pattern
    - Separates versioning from rendering
    - Enables testing versioning independently
    - Allows caching version data
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize template version service.

        SRP: Only version tracking

        Args:
            templates_dir: Templates directory path (injected)
        """
        self.logger = logger
        self.templates_dir = templates_dir

        # Cache for version metadata (performance optimization)
        self._version_cache: Dict[str, Dict[str, Any]] = {}

        self.logger.debug(
            "✅ [TEMPLATE-VERSION] TemplateVersionService initialized (SRP-compliant)"
        )

    def get_template_version_metadata(
        self, template_paths: list[str], use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get version metadata for specified templates.

        BANK-GRADE: SHA-256 hashing for reproducibility

        SRP: Only version metadata generation

        Args:
            template_paths: List of template file paths to track
            use_cache: Whether to use cached metadata

        Returns:
            Dictionary with version metadata for each template
        """
        if not self.templates_dir:
            self.logger.warning("⚠️ [TEMPLATE-VERSION] Templates directory not configured")
            return {}

        self.logger.info(
            f"🔄 [TEMPLATE-VERSION] Generating version metadata for {len(template_paths)} templates"
        )

        metadata = {}

        for template_path in template_paths:
            # Check cache first
            if use_cache and template_path in self._version_cache:
                cached_data = self._version_cache[template_path]
                # Verify file hasn't changed
                if self._is_cache_valid(template_path, cached_data):
                    metadata[template_path] = cached_data
                    continue

            # Generate fresh metadata
            template_metadata = self._generate_metadata_for_template(template_path)
            if template_metadata:
                metadata[template_path] = template_metadata
                self._version_cache[template_path] = template_metadata

        self.logger.info(f"✅ [TEMPLATE-VERSION] Generated metadata for {len(metadata)} templates")

        return metadata

    def get_accountant_view_version_metadata(self) -> dict[str, object]:
        """
        Return legacy Accountant View metadata used by TemplateService reports.

        The broader service metadata includes full hashes and ISO mtimes. This
        wrapper preserves the historical report payload contract: short hash,
        byte size, and raw modified timestamp.
        """
        metadata: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "templates_dir": str(self.templates_dir),
            "template_files": {},
        }

        if not self.templates_dir:
            self.logger.warning("⚠️ [TEMPLATE-VERSION] Templates directory not configured")
            return metadata

        template_files = metadata["template_files"]
        if not isinstance(template_files, dict):
            return metadata

        key_templates = [
            "accountant_view/master_report.html",
            "accountant_view/executive_summary.html",
            "accountant_view/financial_analysis.html",
            "accountant_view/valuation_methodologies.html",
            "accountant_view/valuation_conclusion.html",
        ]

        for template_path in key_templates:
            full_path = self.templates_dir / template_path
            if not full_path.exists():
                continue

            try:
                file_hash = self._calculate_file_hash(full_path)[:16]
                template_files[template_path] = {
                    "hash": file_hash,
                    "size": full_path.stat().st_size,
                    "modified": full_path.stat().st_mtime,
                }
            except Exception as e:
                self.logger.warning(f"Failed to read template {template_path}: {e}")

        return metadata

    def _generate_metadata_for_template(self, template_path: str) -> Optional[Dict[str, Any]]:
        """
        Generate version metadata for single template.

        SRP: Only metadata generation

        Args:
            template_path: Template file path

        Returns:
            Metadata dictionary or None if file not found
        """
        full_path = self.templates_dir / template_path

        if not full_path.exists():
            self.logger.warning(f"⚠️ [TEMPLATE-VERSION] Template not found: {template_path}")
            return None

        try:
            # Calculate SHA-256 hash
            file_hash = self._calculate_file_hash(full_path)

            # Get file size
            file_size = full_path.stat().st_size

            # Get modification time
            mtime = datetime.fromtimestamp(full_path.stat().st_mtime)

            metadata = {
                "hash": file_hash,
                "size": file_size,
                "modified": mtime.isoformat(),
                "algorithm": "SHA-256",
            }

            return metadata

        except Exception as e:
            self.logger.error(
                f"❌ [TEMPLATE-VERSION] Failed to generate metadata for {template_path}: {e}",
                exc_info=True,
            )
            return None

    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA-256 hash of file.

        BANK-GRADE: SHA-256 for security and reproducibility

        SRP: Only hash calculation

        Args:
            file_path: Path to file

        Returns:
            Hex-encoded SHA-256 hash
        """
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read in chunks for large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    def _is_cache_valid(self, template_path: str, cached_data: Dict[str, Any]) -> bool:
        """
        Check if cached metadata is still valid.

        SRP: Only cache validation

        Args:
            template_path: Template file path
            cached_data: Cached metadata

        Returns:
            True if cache is valid
        """
        full_path = self.templates_dir / template_path

        if not full_path.exists():
            return False

        try:
            # Check modification time
            current_mtime = datetime.fromtimestamp(full_path.stat().st_mtime)
            cached_mtime = datetime.fromisoformat(cached_data.get("modified", ""))

            # Cache valid if modification time unchanged
            return current_mtime == cached_mtime

        except Exception:
            return False

    def detect_template_changes(
        self, previous_metadata: Dict[str, Any], template_paths: list[str]
    ) -> Dict[str, str]:
        """
        Detect which templates have changed since previous metadata.

        Args:
            previous_metadata: Previous version metadata
            template_paths: Templates to check

        Returns:
            Dictionary mapping template paths to change status
        """
        current_metadata = self.get_template_version_metadata(
            template_paths, use_cache=False  # Force fresh check
        )

        changes = {}

        for template_path in template_paths:
            if template_path not in current_metadata:
                changes[template_path] = "missing"
                continue

            if template_path not in previous_metadata:
                changes[template_path] = "new"
                continue

            # Compare hashes
            current_hash = current_metadata[template_path].get("hash")
            previous_hash = previous_metadata[template_path].get("hash")

            if current_hash != previous_hash:
                changes[template_path] = "modified"
            else:
                changes[template_path] = "unchanged"

        self.logger.info(
            f"🔍 [TEMPLATE-VERSION] Detected changes: "
            f"{sum(1 for v in changes.values() if v == 'modified')} modified, "
            f"{sum(1 for v in changes.values() if v == 'new')} new, "
            f"{sum(1 for v in changes.values() if v == 'missing')} missing"
        )

        return changes

    def clear_cache(self) -> None:
        """Clear version metadata cache."""
        self._version_cache.clear()
        self.logger.info("✅ [TEMPLATE-VERSION] Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics dictionary
        """
        return {
            "cached_templates": len(self._version_cache),
            "cache_size_bytes": sum(len(str(v)) for v in self._version_cache.values()),
        }
