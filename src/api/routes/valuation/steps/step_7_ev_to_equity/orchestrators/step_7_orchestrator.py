"""
Step 7 Orchestrator

Orchestrates the main execution flow for Step 7 EV to Equity conversion.
"""

from decimal import Decimal
from typing import Any, Dict, Optional


def _has_conflicting_tax_latency_inputs(request: Any) -> bool:
    """True if both legacy tax_latencies and BSA tax_latency rows are present."""
    legacy = bool(getattr(request, "tax_latencies", None))
    if not legacy:
        return False
    bsa = getattr(request, "balance_sheet_adjustments", None) or []
    for adj in bsa:
        cat = getattr(adj, "category", "other") or "other"
        if cat == "tax_latency":
            return True
    return False


from src.domain.report_integrity import build_net_debt_unavailable_warning
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.core.data_extraction_helpers import extract_enum_value
from src.api.routes.valuation.utils.legacy_value_governance import (
    LegacyBridgeLedger,
    resolve_legacy_bridge_ledger,
)

from ...base_step import StepOutput, StepStatus
from ..builders.step_7_result_builder import Step7ResultBuilder
from ..calculators.step_7_equity_calculator import Step7EquityCalculator
from ..handlers.step_7_error_handler import Step7ErrorHandler

logger = get_logger(__name__)


def _unverified_bridge_adjustments_warning(ledger: LegacyBridgeLedger) -> Dict[str, Any]:
    """Disclose bridge rows kept out of the priced equity, sized to what they mean.

    The v1 path never prices a bridge row, so every submitted row lands here.
    Only a row the advisor submitted as accepted (or otherwise decided) makes
    the reported equity differ from what they approved; that stays "high" and
    reaches the Page-1 callout. Auto-proposed rows that nobody accepted, or
    that the advisor declined, leave the value exactly as expected, so they are
    disclosed at "low" and kept off Page 1.
    """
    row_ids = [row.get("id") for row in ledger.unpriced_rows]
    requested_row_ids = [row.get("id") for row in ledger.unpriced_requested_rows]
    details = {
        "step_number": 7,
        "row_ids": row_ids,
        "requested_row_ids": requested_row_ids,
    }
    if requested_row_ids:
        return {
            "type": "unverified_bridge_adjustments",
            "severity": "high",
            "message": (
                "One or more tax-latency or balance-sheet rows are scenario-only "
                "and were excluded from the priced equity value."
            ),
            "recommendation": (
                "Accept/verify each row with evidence, reviewer, timestamp, rule "
                "version, and matching currency before external use."
            ),
            "details": details,
        }
    return {
        "type": "unverified_bridge_adjustments",
        "severity": "low",
        "message": (
            "Proposed tax-latency or balance-sheet rows were not accepted, so they "
            "are not part of the priced equity value; the value does not depend on them."
        ),
        "recommendation": (
            "Review the proposed rows. A row changes the equity value only once it "
            "is accepted with evidence through the governed decision flow."
        ),
        "details": details,
    }


class Step7Orchestrator:
    """Orchestrates the main execution flow for Step 7."""

    def __init__(self, step_name: str):
        """
        Initialize the orchestrator.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name
        self.error_handler = Step7ErrorHandler(step_name)
        self.calculator = Step7EquityCalculator()
        self.result_builder = Step7ResultBuilder(step_name)

    async def orchestrate_execution(
        self, request: object, previous_results: Dict[int, Any], correlation_id: Optional[str]
    ) -> StepOutput:
        """
        Orchestrate the main execution flow.

        Args:
            request: Valuation request
            previous_results: Dictionary of previous step results
            correlation_id: Correlation ID for tracing

        Returns:
            StepOutput with calculation results
        """
        # Find EV source step (priority: Step 6 > 5 > 4 > 3)
        ev_source_step, ev_data = self.calculator.find_ev_source_step(previous_results)

        if not ev_data:
            available_steps = list(previous_results.keys())
            step_statuses = {
                step_num: step_output.status.value if hasattr(step_output, "status") else "unknown"
                for step_num, step_output in previous_results.items()
            }
            return self.error_handler.handle_no_ev_source(available_steps, step_statuses, request)

        logger.info(
            f"📊 Using EV from Step {ev_source_step} (preferred: Step 6 with all discounts)",
            extra={
                "step_number": 7,
                "ev_source_step": ev_source_step,
                "ev_low": ev_data.get("enterprise_value_low"),
                "ev_mid": ev_data.get("enterprise_value_mid"),
                "ev_high": ev_data.get("enterprise_value_high"),
            },
        )

        # Get enterprise values from the source step (convert to Decimal)
        ev_low = to_decimal(ev_data.get("enterprise_value_low", 0))
        ev_mid = to_decimal(ev_data.get("enterprise_value_mid", 0))
        ev_high = to_decimal(ev_data.get("enterprise_value_high", 0))

        # DEBUG: per-step audit; the Step 7 "Calculation Complete" line carries
        # the headline EV→Equity numbers needed for value-chain validation.
        logger.debug(
            "🔍 Step 7: VALUE CHAIN AUDIT - EV Source and Values",
            extra={
                "step_number": 7,
                "ev_source_step": ev_source_step,
                "ev_source_step_name": {
                    3: "Step 3 (Base EV)",
                    4: "Step 4 (Owner Concentration)",
                    5: "Step 5 (Size Discount)",
                    6: "Step 6 (Liquidity Discount)",
                }.get(ev_source_step, f"Step {ev_source_step}"),
                "ev_mid_from_source": to_decimal(ev_mid),
                "ev_low_from_source": to_decimal(ev_low),
                "ev_high_from_source": to_decimal(ev_high),
                "ev_source_keys": list(ev_data.keys()) if ev_data else [],
                "value_chain_step": 7,
                "note": f"EV extracted from Step {ev_source_step}. This EV will be converted to equity value.",
                "correlation_id": correlation_id,
            },
        )

        # Validate EV values
        if ev_mid <= 0 or ev_low < 0 or ev_high <= 0:
            return self.error_handler.handle_invalid_ev_values(
                to_decimal(ev_low),
                to_decimal(ev_mid),
                to_decimal(ev_high),
                ev_source_step,
                list(ev_data.keys()) if ev_data else [],
                request,
            )

        # Extract revenue for operating cash calculation
        revenue = self.calculator.extract_revenue(request, previous_results)

        # Calculate operating cash and excess cash
        operating_cash_data = self.calculator.calculate_operating_cash_and_excess(revenue, request)
        operating_cash = operating_cash_data["operating_cash"]
        operating_cash_pct = operating_cash_data["operating_cash_pct"]
        exemption_applied = operating_cash_data["exemption_applied"]
        exemption_rationale = operating_cash_data["exemption_rationale"]
        business_category = operating_cash_data["business_category"]
        size_tier = operating_cash_data["size_tier"]

        # Extract balance sheet data
        balance_sheet_data = self.calculator.extract_balance_sheet_data(request)
        total_debt = balance_sheet_data["total_debt"]
        cash = balance_sheet_data["cash"]
        balance_sheet_available = balance_sheet_data["balance_sheet_available"]

        # Calculate excess cash
        excess_cash = self.calculator.equity_converter.calculate_excess_cash(cash, operating_cash)

        # Log if using defaults
        if not balance_sheet_available:
            logger.info(
                "⚠️  Balance sheet data not available, assuming net debt = 0",
                extra={"ev_mid": to_decimal(ev_mid)},
            )

        # Log operating cash exemption if applied
        if exemption_applied:
            logger.info(
                f"📊 Operating cash exemption applied: {operating_cash_pct:.1f}% of revenue = €{to_decimal(operating_cash):,.0f}",
                extra={
                    "revenue": to_decimal(revenue),
                    "operating_cash": to_decimal(operating_cash),
                    "operating_cash_pct": operating_cash_pct,
                    "total_cash": to_decimal(cash),
                    "excess_cash": to_decimal(excess_cash),
                    "business_category": extract_enum_value(business_category),
                    "exemption_rationale": exemption_rationale,
                },
            )

        # Validate balance sheet data
        balance_sheet_validation = self.calculator.validate_balance_sheet_data(
            total_debt, cash, ev_mid
        )

        # Log validation warnings
        for warning in balance_sheet_validation.get("warnings", []):
            logger.warning(f"Balance sheet validation warning: {warning}")

        # Calculate net debt — DEBUG: the Step 7 Calculation Complete log
        # carries the resulting net_debt figure.
        logger.debug(
            "🧮 Calculating Net Debt",
            extra={
                "step_number": 7,
                "total_debt": to_decimal(total_debt),
                "cash": to_decimal(cash),
                "operating_cash": to_decimal(operating_cash),
                "excess_cash": to_decimal(excess_cash),
                "exemption_applied": exemption_applied,
                "formula_standard": f"Net Debt = Total Debt {to_decimal(total_debt):,.0f} - Cash {to_decimal(cash):,.0f}",
                "formula_exemption": (
                    f"Net Debt = Total Debt {to_decimal(total_debt):,.0f} - Excess Cash {to_decimal(excess_cash):,.0f}"
                    if exemption_applied
                    else None
                ),
            },
        )

        net_debt = self.calculator.calculate_net_debt(
            total_debt, cash, excess_cash, exemption_applied
        )

        logger.debug(
            "✅ Net Debt calculated",
            extra={
                "step_number": 7,
                "net_debt": to_decimal(net_debt),
                "calculation": f'Total Debt {to_decimal(total_debt):,.0f} - {"Excess Cash" if exemption_applied else "Cash"} {to_decimal(excess_cash if exemption_applied else cash):,.0f} = {to_decimal(net_debt):,.0f}',
                "exemption_applied": exemption_applied,
                "exemption_rationale": exemption_rationale if exemption_applied else None,
            },
        )

        # NWC Normalization: calculate surplus/deficit for equity bridge
        nwc_normalization = None
        nwc_surplus_adjustment = to_decimal("0")
        try:
            from src.domain.nwc_normalizer import NWCNormalizer

            historical = getattr(request, "historical_years_data", None) or []
            current_yd = getattr(request, "current_year_data", None)
            if len(historical) >= 1:
                normalizer = NWCNormalizer()
                nwc_normalization = normalizer.normalize(historical, current_yd)
                if nwc_normalization is not None:
                    nwc_surplus_adjustment = nwc_normalization.surplus_deficit
                    logger.info(
                        "NWC normalization calculated for equity bridge",
                        extra={
                            "step_number": 7,
                            "target_nwc_pct": float(nwc_normalization.target_nwc_pct),
                            "actual_nwc_pct": float(nwc_normalization.actual_nwc_pct),
                            "surplus_deficit": float(nwc_surplus_adjustment),
                            "is_surplus": nwc_normalization.is_surplus,
                            "years_analyzed": nwc_normalization.years_analyzed,
                        },
                    )
        except Exception as nwc_err:
            logger.warning("NWC normalization failed (non-critical)", error=str(nwc_err))

        # Convert to equity value — DEBUG: per-stage progress.
        logger.debug(
            "🧮 Converting Enterprise Value to Equity Value",
            extra={
                "step_number": 7,
                "ev_low": to_decimal(ev_low),
                "ev_mid": to_decimal(ev_mid),
                "ev_high": to_decimal(ev_high),
                "net_debt": to_decimal(net_debt),
                "nwc_adjustment": to_decimal(nwc_surplus_adjustment),
                "formula": "Equity Value = Enterprise Value - Net Debt + NWC Surplus/Deficit",
                "calculation_low": f"{to_decimal(ev_low):,.0f} - {to_decimal(net_debt):,.0f} + {to_decimal(nwc_surplus_adjustment):,.0f}",
                "calculation_mid": f"{to_decimal(ev_mid):,.0f} - {to_decimal(net_debt):,.0f} + {to_decimal(nwc_surplus_adjustment):,.0f}",
                "calculation_high": f"{to_decimal(ev_high):,.0f} - {to_decimal(net_debt):,.0f} + {to_decimal(nwc_surplus_adjustment):,.0f}",
            },
        )

        equity_values = self.calculator.convert_to_equity(ev_low, ev_mid, ev_high, net_debt)

        equity_value_low = equity_values["equity_low"] + nwc_surplus_adjustment
        equity_value_mid = equity_values["equity_mid"] + nwc_surplus_adjustment
        equity_value_high = equity_values["equity_high"] + nwc_surplus_adjustment

        # Fail closed: only accepted/verified, evidence-linked, reviewed,
        # versioned, same-currency rows may alter the operational v1 value.
        bridge_ledger = resolve_legacy_bridge_ledger(request)
        equity_value_low += bridge_ledger.total
        equity_value_mid += bridge_ledger.total
        equity_value_high += bridge_ledger.total
        merged_tax_latencies = bridge_ledger.priced_tax_rows
        bs_adjustments_applied = bridge_ledger.priced_balance_sheet_rows
        combined_tax_latency_total = bridge_ledger.tax_total

        if bridge_ledger.total:
            logger.info(
                "Governed v1 equity-bridge adjustments applied",
                extra={
                    "step_number": 7,
                    "tax_latency_total": from_decimal(bridge_ledger.tax_total, 2),
                    "balance_sheet_adjustment_total": from_decimal(
                        bridge_ledger.balance_sheet_total, 2
                    ),
                    "equity_mid_after": from_decimal(equity_value_mid, 2),
                },
            )

        # Store original calculated values (before flooring) for edge case analysis
        calculated_equity_low = equity_value_low
        calculated_equity_mid = equity_value_mid
        calculated_equity_high = equity_value_high

        # Validate equity range
        range_validation = self.calculator.validate_equity_range(
            equity_value_low, equity_value_mid, equity_value_high
        )

        equity_value_low = range_validation["equity_low"]
        equity_value_mid = range_validation["equity_mid"]
        equity_value_high = range_validation["equity_high"]
        range_validated = range_validation["range_validated"]
        range_corrected = range_validation["range_corrected"]

        if range_corrected:
            logger.warning(
                "⚠️  Equity range was invalid and has been auto-corrected",
                extra={
                    "original_low": to_decimal(range_validation["original_values"]["equity_low"]),
                    "original_mid": to_decimal(range_validation["original_values"]["equity_mid"]),
                    "original_high": to_decimal(range_validation["original_values"]["equity_high"]),
                    "corrected_low": to_decimal(equity_value_low),
                    "corrected_mid": to_decimal(equity_value_mid),
                    "corrected_high": to_decimal(equity_value_high),
                },
            )

        # Get edge case notes
        edge_case_notes = self.calculator.get_edge_case_notes(
            calculated_equity_mid, total_debt, cash, ev_mid, net_debt
        )

        # Floor equity values at 0 for display (negative equity indicates over-leverage)
        equity_value_low = max(to_decimal("0"), equity_value_low)
        equity_value_mid = max(to_decimal("0"), equity_value_mid)
        equity_value_high = max(to_decimal("0"), equity_value_high)

        # Log warning if calculated equity would be negative
        if calculated_equity_mid < 0:
            logger.warning(
                "⚠️  Equity value would be negative (high debt), floored at 0",
                extra={
                    "ev_mid": to_decimal(ev_mid),
                    "total_debt": to_decimal(total_debt),
                    "cash": to_decimal(cash),
                    "net_debt": to_decimal(net_debt),
                    "calculated_equity": to_decimal(calculated_equity_mid),
                    "displayed_equity": to_decimal(equity_value_mid),
                    "note": "Equity value is negative because total debt exceeds enterprise value. "
                    "This indicates the company is over-leveraged.",
                },
            )

        # Round to 2 decimal places for currency precision
        equity_value_low = bank_round(equity_value_low, 2)
        equity_value_mid = bank_round(equity_value_mid, 2)
        equity_value_high = bank_round(equity_value_high, 2)

        # Get conversion breakdown for metadata
        conversion_breakdown = self.calculator.get_conversion_breakdown(
            ev_low,
            ev_mid,
            ev_high,
            total_debt,
            cash,
            net_debt,
            equity_value_low,
            equity_value_mid,
            equity_value_high,
        )

        # Convert to float for JSON serialization
        ev_low_float = from_decimal(ev_low, 2)
        ev_mid_float = from_decimal(ev_mid, 2)
        ev_high_float = from_decimal(ev_high, 2)
        total_debt_float = from_decimal(total_debt, 2)
        cash_float = from_decimal(cash, 2)
        net_debt_float = from_decimal(net_debt, 2)
        equity_low_float = from_decimal(equity_value_low, 2)
        equity_mid_float = from_decimal(equity_value_mid, 2)
        equity_high_float = from_decimal(equity_value_high, 2)
        calculated_equity_mid_float = from_decimal(calculated_equity_mid, 2)

        # DEBUG: per-step audit dump; Step 7 "Calculation Complete" carries headline.
        logger.debug(
            "🔍 Step 7: VALUE CHAIN AUDIT - Equity Value Output",
            extra={
                "step_number": 7,
                "equity_value_mid": equity_mid_float,
                "equity_value_low": equity_low_float,
                "equity_value_high": equity_high_float,
                "enterprise_value_mid": ev_mid_float,
                "net_debt": net_debt_float,
                "calculation": f"{ev_mid_float:,.0f} - {net_debt_float:,.0f} = {equity_mid_float:,.0f}",
                "value_chain_step": 7,
                "next_step": "Step 8 (Ownership Adjustment) or Step 10 (Range Methodology)",
                "note": "This equity_value_mid MUST be preserved in Step 10 as valuation_mid",
                "correlation_id": correlation_id,
            },
        )

        # Comprehensive summary logging
        logger.info(
            "📊 Step 7: EV to Equity Conversion - Calculation Complete",
            extra={
                "step_number": 7,
                "step_name": "EV to Equity Conversion",
                "status": "COMPLETED",
                "inputs": {
                    "enterprise_value_low": ev_low_float,
                    "enterprise_value_mid": ev_mid_float,
                    "enterprise_value_high": ev_high_float,
                    "cash": cash_float,
                    "balance_sheet_available": balance_sheet_available,
                },
                "calculation": {
                    "formula": "Equity Value = Enterprise Value - Net Debt",
                    "net_debt_formula": (
                        "Net Debt = Total Debt - Cash"
                        if not exemption_applied
                        else "Net Debt = Total Debt - Excess Cash"
                    ),
                    "net_debt": net_debt_float,
                    "exemption_applied": exemption_applied,
                    "operating_cash": to_decimal(operating_cash) if exemption_applied else None,
                    "excess_cash": to_decimal(excess_cash) if exemption_applied else None,
                },
                "outputs": {
                    "equity_value_low": equity_low_float,
                    "equity_value_mid": equity_mid_float,
                    "equity_value_high": equity_high_float,
                    "calculated_equity_mid": calculated_equity_mid_float,
                },
            },
        )

        # DEBUG: dup of "📊 Step 7: EV to Equity Conversion - Calculation Complete" above.
        logger.debug(
            f"✓ EV to Equity conversion complete",
            extra={
                "ev_source_step": ev_source_step,
                "ev_mid": ev_mid_float,
                "total_debt": total_debt_float,
                "cash": cash_float,
                "operating_cash": to_decimal(operating_cash),
                "excess_cash": to_decimal(excess_cash),
                "net_debt": net_debt_float,
                "equity_value_mid": equity_mid_float,
                "calculated_equity_mid": calculated_equity_mid_float,
                "balance_sheet_available": balance_sheet_available,
                "exemption_applied": exemption_applied,
                "range_validated": range_validated,
                "range_corrected": range_corrected,
                "formula": f"{ev_mid_float:,.0f} - {net_debt_float:,.0f} = {equity_mid_float:,.0f}",
                "precision": "Decimal (bank-grade)",
            },
        )

        # Build result and metadata
        result_dict = self.result_builder.build_result_dict(
            equity_low_float,
            equity_mid_float,
            equity_high_float,
            total_debt_float,
            cash_float,
            operating_cash,
            excess_cash,
            net_debt_float,
            balance_sheet_available,
            ev_source_step,
            calculated_equity_mid_float,
            range_validated,
            range_corrected,
            exemption_applied,
        )

        metadata_dict = self.result_builder.build_metadata_dict(
            ev_low_float,
            ev_mid_float,
            ev_high_float,
            total_debt_float,
            cash_float,
            operating_cash,
            excess_cash,
            operating_cash_pct,
            net_debt_float,
            equity_low_float,
            equity_mid_float,
            equity_high_float,
            ev_source_step,
            exemption_applied,
            exemption_rationale,
            size_tier,
            business_category,
            range_validated,
            range_corrected,
            balance_sheet_validation,
            edge_case_notes,
            calculated_equity_mid_float,
            conversion_breakdown,
        )

        # Attach NWC normalization data to result for report generation and frontend
        if nwc_normalization is not None:
            result_dict["nwc_normalization"] = nwc_normalization.to_dict()
            result_dict["nwc_surplus_deficit"] = from_decimal(nwc_surplus_adjustment, 2)
            metadata_dict["nwc_target_pct"] = float(nwc_normalization.target_nwc_pct)
            metadata_dict["nwc_actual_pct"] = float(nwc_normalization.actual_nwc_pct)
            metadata_dict["nwc_surplus_deficit"] = float(nwc_surplus_adjustment)

        # Attach tax latency data to result for report generation (legacy + BSA tax_latency rows)
        if merged_tax_latencies:
            result_dict["tax_latencies"] = merged_tax_latencies
            result_dict["tax_latency_total"] = from_decimal(combined_tax_latency_total, 2)
            metadata_dict["tax_latency_count"] = len(merged_tax_latencies)
            metadata_dict["tax_latency_total"] = from_decimal(combined_tax_latency_total, 2)

        # Attach balance sheet adjustments to result for report generation
        if bs_adjustments_applied:
            result_dict["balance_sheet_adjustments"] = bs_adjustments_applied

        if bridge_ledger.all_rows:
            result_dict["equity_bridge_adjustment_ledger"] = {
                "version": "legacy_v1_equity_bridge_governance.v1",
                "value_basis": "equity_value",
                "currency": getattr(request, "currency", None),
                "rows": bridge_ledger.all_rows,
                "tax_latency_net_impact": from_decimal(bridge_ledger.tax_total, 2),
                "balance_sheet_adjustment_net_impact": from_decimal(
                    bridge_ledger.balance_sheet_total, 2
                ),
                "total_net_impact": from_decimal(bridge_ledger.total, 2),
            }

        governance_warnings = list(
            (getattr(request, "metadata", None) or {}).get("legacy_value_governance_warnings", [])
            if isinstance(getattr(request, "metadata", None), dict)
            else []
        )
        if bridge_ledger.unpriced_rows:
            result_dict["unpriced_bridge_adjustments"] = bridge_ledger.unpriced_rows
            governance_warnings.append(_unverified_bridge_adjustments_warning(bridge_ledger))
        if governance_warnings:
            existing_warnings = result_dict.get("data_quality_warnings")
            if isinstance(existing_warnings, list):
                existing_warnings.extend(governance_warnings)
            else:
                result_dict["data_quality_warnings"] = governance_warnings

        # Pass-8: integrity disclosure — when the EV→Equity bridge had to
        # assume net debt = 0 because no balance-sheet data was provided,
        # surface a high-severity warning so the PDF reader knows the bridge
        # is a proxy. The aggregator picks this up via result["data_quality_warnings"].
        if not balance_sheet_available:
            existing = result_dict.get("data_quality_warnings")
            integrity = build_net_debt_unavailable_warning()
            if isinstance(existing, list):
                existing.append(integrity)
            else:
                result_dict["data_quality_warnings"] = [integrity]

        return StepOutput(
            step_number=7,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=result_dict,
            metadata=metadata_dict,
        )
