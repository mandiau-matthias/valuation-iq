"""SOTP-trigger foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationSotpTriggerFields:
    # =========================================================================
    # SOTP-TRIGGER WARNING (Executive Summary callout)
    # =========================================================================
    # Fires when a stand-alone valuation produces a non-defensible result
    # (e.g. negative equity from net debt > implied EV — the classic signal
    # that a Sum-of-the-Parts treatment is required). Surfaces the gap to
    # the reader instead of letting a misleading number stand.
    sotp_trigger_title: str
    sotp_trigger_text: str

