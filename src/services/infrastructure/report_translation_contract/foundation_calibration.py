"""Calibration-page foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationCalibrationFields:
    # =========================================================================
    # CALIBRATION PAGE (~25 strings)
    # =========================================================================

    calib_title: str
    calib_sde_intro: str
    calib_dcf_intro: str
    calib_hybrid_intro: str
    calib_asset_intro: str
    calib_yield_intro: str
    calib_multiples_intro: str
    calib_multiple_applied: str
    calib_multiple_range: str
    calib_methodology_label: str
    calib_sde_market_median: str
    calib_dcf_calculated_value: str
    calib_market_median: str
    calib_dcf_market_validation: str
    calib_risk_discounts: str
    calib_dcf_final_value: str
    calib_applied: str
    calib_asset_basis_label: str
    calib_asset_basis_value: str
    calib_asset_adjustments_label: str
    calib_asset_adjustments_value: str
    calib_asset_final_label: str
    calib_yield_basis_label: str
    calib_yield_basis_value: str
    calib_yield_adjustments_label: str
    calib_yield_adjustments_value: str
    calib_yield_final_label: str
    calib_sde_badge: str
    calib_dcf_badge: str
    calib_hybrid_badge: str
    calib_asset_badge: str
    calib_yield_badge: str
    calib_adaptive_lens_intro: str
    calib_adaptive_lens_badge: str
    #: 2026-05-27: when Adaptive runs multiples-only (DCF excluded), the
    #: base intro's "DCF-crosscheck ondersteunt de bandbreedte intern" is
    #: factually wrong (no DCF ran). These variants reframe the page.
    calib_adaptive_lens_intro_multiples_only: str
    calib_adaptive_lens_badge_multiples_only: str
    calib_full_calculation: str
    calib_sde_bottom_text: str
    calib_dcf_bottom_text: str
    calib_multiples_bottom_text: str
    calib_ref_market_band: str
    calib_ref_market_band_reference_only: str
    calib_ref_size_discount: str
    calib_ref_size_discount_skipped: str
    calib_ref_illiquidity: str
    calib_dcf_sensitivity_title: str
    calib_dcf_wacc_label: str
    calib_dcf_terminal_growth: str
    calib_dcf_exit_multiple: str
    calib_dcf_projection_years: str
    calib_dcf_terminal_methodology_label: str
    calib_dcf_terminal_method_gordon: str
    calib_dcf_terminal_method_exit_multiple: str
    calib_dcf_sensitivity_note_gordon: str
    calib_dcf_sensitivity_note_exit_multiple: str
    calib_dcf_terminal_value_note_gordon: str
    calib_dcf_terminal_value_note_exit_multiple: str
    calib_dcf_wacc_buildup_label: str
    calib_dcf_mid_year_label: str
    calib_dcf_mid_year_note: str
    calib_dcf_year_end_note: str
    calib_dcf_academic_coe_label: str
    calib_dcf_terminal_split_label: str
    calib_dcf_explicit_period_label: str
    calib_dcf_terminal_period_label: str

