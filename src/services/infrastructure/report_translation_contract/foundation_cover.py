"""Cover-page foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationCoverFields:
    # =========================================================================
    # COVER PAGE (~15 strings)
    # =========================================================================

    cover_estimate_label: str
    cover_estimate_label_seller: str
    cover_ev_label: str
    cover_equity_label: str
    cover_equity_note: str
    equity_adjusted_label: str
    equity_adjusted_note: str
    cover_ebitda_label: str
    cover_sde_label: str
    cover_multiple_label: str
    cover_wacc_label: str
    cover_date_label: str
    cover_confidential: str
    cover_founded: str
    cover_year_suffix: str
    cover_years_suffix: str
    cover_ev_note_dcf: str
    cover_ev_note_hybrid: str
    #: EV footnote when engine is hybrid internally but report lens is Upswitch Adaptive (Pass-9).
    cover_ev_note_adaptive: str
    #: 2026-05-27: EV footnote variant for the Adaptive run where DCF was excluded
    #: (revenue < €5M); discloses the multiples-only lens on the cover.
    cover_ev_note_adaptive_multiples_only: str
    cover_ev_note_default: str
    #: Cover bottom-bar middle stat label — fires on Adaptive hybrid blends
    #: in place of "Applied Multiple" so the cover doesn't read as a
    #: single-multiple call when DCF leg contributed materially.
    cover_adaptive_blend_label: str
    #: Phase 5 — non-EUR statutory currency disclosure on the cover.
    cover_statutory_currency_label: str
    cover_statutory_currency_note: str
    #: Owner-profiling disclosure line on cover — placeholders: {tri}, {risk_level}, {adj_pct}
    cover_owner_profiling_summary: str

