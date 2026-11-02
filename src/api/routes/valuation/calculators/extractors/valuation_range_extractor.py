"""
Valuation Range Extractor

Extracts valuation range from step results with priority handling.
"""

from decimal import Decimal

from src.utils.valuation_logger import ValuationLogger


class ValuationRangeExtractor:
    """Extracts valuation range from step results."""
    
    def __init__(self, logger: ValuationLogger):
        self.logger = logger
    
    def extract_range(
        self,
        step_10: dict[str, object],
        step_11: dict[str, object],
        equity_value: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Extract valuation range with priority: Step 11 > Step 10 > Step 7 (for mid only).
        
        Args:
            step_10: Step 10 result dictionary
            step_11: Step 11 result dictionary
            equity_value: Equity value from Step 7 (fallback for mid)
            
        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high)
        """
        # Extract from Step 11 (highest priority)
        step_11_low = step_11.get("valuation_low") if step_11 else None
        step_11_mid = step_11.get("valuation_mid") if step_11 else None
        step_11_high = step_11.get("valuation_high") if step_11 else None
        
        # Extract from Step 10 (fallback)
        step_10_low = step_10.get("valuation_low") if step_10 else None
        step_10_mid = step_10.get("valuation_mid") if step_10 else None
        step_10_high = step_10.get("valuation_high") if step_10 else None
        
        valuation_low = step_11_low if step_11_low is not None else (step_10_low if step_10_low is not None else Decimal("0.0"))
        valuation_mid = step_11_mid if step_11_mid is not None else (step_10_mid if step_10_mid is not None else equity_value)
        valuation_high = step_11_high if step_11_high is not None else (step_10_high if step_10_high is not None else Decimal("0.0"))
        
        # Log which step's values are being used
        if step_11_low is not None and step_11_mid is not None and step_11_high is not None:
            self.logger.debug(
                "✅ Using valuation range from Step 11",
                extra={
                    "valuation_low": str(valuation_low),
                    "valuation_mid": str(valuation_mid),
                    "valuation_high": str(valuation_high),
                }
            )
        elif step_10_low is not None and step_10_mid is not None and step_10_high is not None:
            self.logger.info(
                "✅ Using valuation range from Step 10",
                extra={
                    "valuation_low": str(valuation_low),
                    "valuation_mid": str(valuation_mid),
                    "valuation_high": str(valuation_high),
                }
            )
        else:
            self.logger.warning(
                "⚠️ Using equity value as valuation_mid (Step 10/11 unavailable)",
                extra={
                    "valuation_low": str(valuation_low),
                    "valuation_mid": str(valuation_mid),
                    "valuation_high": str(valuation_high),
                    "equity_value": str(equity_value),
                }
            )
        
        return valuation_low, valuation_mid, valuation_high
