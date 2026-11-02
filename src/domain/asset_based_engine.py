"""
Asset-Based Valuation Engine

Implements the Asset Approach for business valuation, which values a company
based on the fair market value of its assets minus liabilities.

ACADEMIC FOUNDATION:
- Hitchner, J.R. (2017): "Financial Valuation" Ch. 8 - Asset-Based Approach
- Pratt, S.P. & Niculita, A.V. (2008): "Valuing a Business" - Asset Methods
- USPAP Standards 9-10: Asset-Based Business Valuation
- IVS 200: Business Valuation Standards

WHEN TO USE ASSET-BASED VALUATION:
1. Manufacturing/construction with significant PP&E
2. Real estate holding companies
3. Investment/holding companies
4. Distressed businesses (going concern doubt)
5. Liquidation scenarios
6. Asset-heavy businesses with low earnings

METHODS IMPLEMENTED:
1. Adjusted Book Value (Going Concern)
   - Fair Market Value of Assets - Fair Market Value of Liabilities
   - Used when business will continue operating

2. Orderly Liquidation Value
   - Assets sold over reasonable time period (6-12 months)
   - Typically 60-80% of FMV

3. Forced Liquidation Value
   - Assets sold immediately (auction)
   - Typically 30-50% of FMV

4. Replacement Cost Method
   - Cost to recreate the business from scratch
   - Used as ceiling for acquisition price

ASSET ADJUSTMENTS:
- Accounts Receivable: Bad debt reserve (typically 2-10%)
- Inventory: Obsolescence reserve (industry-specific)
- PP&E: Appraisal to Fair Market Value
- Intangibles: Customer lists, patents, goodwill
- Real Estate: Market value vs. book value

@author UpSwitch CTO Team
@date January 2026
@version 1.0.0
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal, bank_round
from src.domain.models import FinancialData, ConfidenceLevel

logger = get_logger(__name__)


class AssetValuationMethod(str, Enum):
    """Asset-based valuation methods."""
    ADJUSTED_BOOK_VALUE = "adjusted_book_value"
    ORDERLY_LIQUIDATION = "orderly_liquidation"
    FORCED_LIQUIDATION = "forced_liquidation"
    REPLACEMENT_COST = "replacement_cost"


# ============================================================================
# LIQUIDATION FACTORS BY ASSET TYPE
# Source: Pratt & Niculita (2008), Industry data
# ============================================================================
LIQUIDATION_FACTORS = {
    # Orderly Liquidation (6-12 months to sell)
    "orderly": {
        "cash": Decimal("1.00"),           # Cash is cash
        "accounts_receivable": Decimal("0.85"),  # Collection discount
        "inventory": Decimal("0.65"),       # Markdown for quick sale
        "equipment": Decimal("0.50"),       # Used equipment market
        "vehicles": Decimal("0.60"),        # Vehicle auction
        "real_estate": Decimal("0.90"),     # Real estate holds value
        "intangibles": Decimal("0.20"),     # Intangibles hard to sell
        "other_assets": Decimal("0.50"),    # General discount
    },
    # Forced Liquidation (immediate auction)
    "forced": {
        "cash": Decimal("1.00"),
        "accounts_receivable": Decimal("0.60"),
        "inventory": Decimal("0.35"),
        "equipment": Decimal("0.25"),
        "vehicles": Decimal("0.40"),
        "real_estate": Decimal("0.70"),
        "intangibles": Decimal("0.05"),
        "other_assets": Decimal("0.25"),
    },
}

# Typical adjustments to book value by industry
# Source: Industry M&A data, appraisal reports
BOOK_VALUE_ADJUSTMENTS = {
    "manufacturing": {
        "equipment_markup": Decimal("1.10"),     # Specialized equipment may be worth more
        "inventory_markdown": Decimal("0.85"),    # Inventory obsolescence
        "receivables_discount": Decimal("0.95"),  # Bad debt reserve
    },
    "construction": {
        "equipment_markup": Decimal("1.05"),
        "inventory_markdown": Decimal("0.90"),
        "receivables_discount": Decimal("0.90"),  # Higher bad debt for construction
    },
    "retail": {
        "equipment_markup": Decimal("0.70"),      # Retail fixtures low resale
        "inventory_markdown": Decimal("0.60"),    # Fashion/seasonal obsolescence
        "receivables_discount": Decimal("0.98"),
    },
    "technology": {
        "equipment_markup": Decimal("0.50"),      # Tech equipment depreciates fast
        "inventory_markdown": Decimal("0.40"),    # Tech inventory obsoletes quickly
        "receivables_discount": Decimal("0.95"),
    },
    "services": {
        "equipment_markup": Decimal("0.80"),
        "inventory_markdown": Decimal("0.90"),
        "receivables_discount": Decimal("0.92"),
    },
    # Real-estate patrimonium / asset-holding entities — book value is the
    # floor unless an appraisal is provided. Equipment-grade depreciation
    # (0.85x) is inappropriate for real estate, which holds value far better
    # than office furniture and machinery. The substring matcher in
    # `_get_industry_adjustments` lets these aliases catch fixture strings
    # `real_estate_holding`, `patrimony`, `patrimonium`, `vastgoed`.
    "real_estate_holding": {
        "equipment_markup": Decimal("1.00"),
        "inventory_markdown": Decimal("1.00"),
        "receivables_discount": Decimal("1.00"),
    },
    "patrimony": {
        "equipment_markup": Decimal("1.00"),
        "inventory_markdown": Decimal("1.00"),
        "receivables_discount": Decimal("1.00"),
    },
    "patrimonium": {
        "equipment_markup": Decimal("1.00"),
        "inventory_markdown": Decimal("1.00"),
        "receivables_discount": Decimal("1.00"),
    },
    "vastgoed": {
        "equipment_markup": Decimal("1.00"),
        "inventory_markdown": Decimal("1.00"),
        "receivables_discount": Decimal("1.00"),
    },
    "default": {
        "equipment_markup": Decimal("0.85"),
        "inventory_markdown": Decimal("0.80"),
        "receivables_discount": Decimal("0.95"),
    },
}


@dataclass
class AssetAdjustment:
    """Individual asset adjustment for transparency."""
    asset_type: str
    book_value: Decimal
    adjustment_factor: Decimal
    adjusted_value: Decimal
    rationale: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_type": self.asset_type,
            "book_value": from_decimal(self.book_value),
            "adjustment_factor": from_decimal(self.adjustment_factor),
            "adjusted_value": from_decimal(self.adjusted_value),
            "rationale": self.rationale,
        }


@dataclass
class AssetBasedResult:
    """
    Result of asset-based valuation.
    """
    # Method used
    method: AssetValuationMethod
    
    # Book values
    total_assets_book: Decimal
    total_liabilities_book: Decimal
    net_book_value: Decimal
    
    # Adjusted values
    total_assets_adjusted: Decimal
    total_liabilities_adjusted: Decimal
    net_asset_value: Decimal
    
    # Breakdown
    asset_adjustments: List[AssetAdjustment] = field(default_factory=list)
    
    # Intangibles (separate for transparency)
    tangible_asset_value: Decimal = Decimal("0")
    intangible_asset_value: Decimal = Decimal("0")
    
    # Value range
    value_low: Decimal = Decimal("0")
    value_high: Decimal = Decimal("0")
    
    # Metadata
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    methodology: str = "Asset-Based"
    sources: List[str] = field(default_factory=list)
    rationale: str = ""
    warnings: List[str] = field(default_factory=list)
    industry: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method.value,
            "total_assets_book": from_decimal(self.total_assets_book),
            "total_liabilities_book": from_decimal(self.total_liabilities_book),
            "net_book_value": from_decimal(self.net_book_value),
            "total_assets_adjusted": from_decimal(self.total_assets_adjusted),
            "total_liabilities_adjusted": from_decimal(self.total_liabilities_adjusted),
            "net_asset_value": from_decimal(self.net_asset_value),
            "asset_adjustments": [a.to_dict() for a in self.asset_adjustments],
            "tangible_asset_value": from_decimal(self.tangible_asset_value),
            "intangible_asset_value": from_decimal(self.intangible_asset_value),
            "value_low": from_decimal(self.value_low),
            "value_high": from_decimal(self.value_high),
            "confidence": self.confidence.value,
            "methodology": self.methodology,
            "sources": self.sources,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "industry": self.industry,
        }


class AssetBasedEngine:
    """
    Asset-Based Valuation Engine.
    
    Values a company based on the fair market value of its assets
    minus fair market value of liabilities.
    
    Usage:
        engine = AssetBasedEngine(financial_data)
        result = engine.calculate_adjusted_book_value(industry="manufacturing")
        liquidation = engine.calculate_liquidation_value(orderly=True)
    """
    
    def __init__(
        self,
        financial_data: FinancialData,
        country_code: str = "BE",
    ):
        """
        Initialize Asset-Based Engine.
        
        Args:
            financial_data: Company financial data with balance sheet
            country_code: ISO country code
        """
        self.financial_data = financial_data
        self.country_code = country_code
        self.current_year = financial_data.current_year
        
        # Validate balance sheet data availability
        self._validate_balance_sheet()
        
        logger.info(
            f"AssetBasedEngine initialized",
            company=financial_data.company_name,
            total_assets=from_decimal(self.current_year.total_assets or Decimal("0")),
            country=country_code,
        )
    
    def _validate_balance_sheet(self) -> None:
        """Validate that balance sheet data is available."""
        year_data = self.current_year
        
        if year_data.total_assets is None or year_data.total_assets <= Decimal("0"):
            logger.warning(
                "Total assets not provided or zero - asset-based valuation may be inaccurate"
            )
        
        if year_data.total_liabilities is None:
            logger.warning(
                "Total liabilities not provided - will estimate from available data"
            )
    
    def _get_industry_adjustments(self, industry: str) -> Dict[str, Decimal]:
        """Get book value adjustments for industry."""
        industry_norm = industry.lower().strip()
        
        # Match industry to adjustment table
        for key in BOOK_VALUE_ADJUSTMENTS:
            if key in industry_norm or industry_norm in key:
                return BOOK_VALUE_ADJUSTMENTS[key]
        
        return BOOK_VALUE_ADJUSTMENTS["default"]
    
    def calculate_adjusted_book_value(
        self,
        industry: str,
        equipment_fmv_factor: Optional[Decimal] = None,
        inventory_fmv_factor: Optional[Decimal] = None,
        receivables_collection_rate: Optional[Decimal] = None,
        real_estate_fmv: Optional[Decimal] = None,
        intangible_value: Optional[Decimal] = None,
        other_revaluations: Optional[Decimal] = None,
    ) -> AssetBasedResult:
        """
        Calculate Adjusted Book Value (Going Concern).
        
        Adjusts book values to Fair Market Value while assuming
        the business continues operating.
        
        Args:
            industry: Business industry
            equipment_fmv_factor: Factor to adjust equipment (1.0 = book value)
            inventory_fmv_factor: Factor to adjust inventory
            receivables_collection_rate: Expected collection rate (0-1)
            real_estate_fmv: Override FMV for real estate if known
            intangible_value: Separately appraised intangible value
            
        Returns:
            AssetBasedResult with adjusted values
        """
        year_data = self.current_year
        adjustments = self._get_industry_adjustments(industry)
        asset_adjustments = []
        warnings = []
        
        # Get book values
        total_assets_book = (
            year_data.total_assets if year_data.total_assets is not None else Decimal("0")
        )
        total_liabilities_book = (
            year_data.total_liabilities
            if year_data.total_liabilities is not None
            else Decimal("0")
        )
        
        if total_assets_book <= Decimal("0"):
            warnings.append("Total assets not provided - using estimated values")
            # Estimate from revenue (typical asset turnover ~1.5x for SMEs)
            total_assets_book = year_data.revenue / Decimal("1.5")
        
        # Component adjustments
        adjusted_total = Decimal("0")
        
        # 1. Cash and equivalents (no adjustment)
        cash = year_data.cash if year_data.cash is not None else Decimal("0")
        adjusted_total += cash
        asset_adjustments.append(AssetAdjustment(
            asset_type="Cash & Equivalents",
            book_value=cash,
            adjustment_factor=Decimal("1.0"),
            adjusted_value=cash,
            rationale="Cash at face value"
        ))
        
        # 2. Accounts Receivable
        ar = (
            year_data.accounts_receivable
            if year_data.accounts_receivable is not None
            else total_assets_book * Decimal("0.20")
        )
        ar_factor = (
            receivables_collection_rate
            if receivables_collection_rate is not None
            else adjustments["receivables_discount"]
        )
        ar_adjusted = ar * ar_factor
        adjusted_total += ar_adjusted
        asset_adjustments.append(AssetAdjustment(
            asset_type="Accounts Receivable",
            book_value=ar,
            adjustment_factor=ar_factor,
            adjusted_value=ar_adjusted,
            rationale=f"Net realizable value ({from_decimal(ar_factor * 100):.0f}% collection rate)"
        ))
        
        # 3. Inventory
        inventory = (
            year_data.inventory
            if year_data.inventory is not None
            else total_assets_book * Decimal("0.15")
        )
        inv_factor = (
            inventory_fmv_factor
            if inventory_fmv_factor is not None
            else adjustments["inventory_markdown"]
        )
        inv_adjusted = inventory * inv_factor
        adjusted_total += inv_adjusted
        asset_adjustments.append(AssetAdjustment(
            asset_type="Inventory",
            book_value=inventory,
            adjustment_factor=inv_factor,
            adjusted_value=inv_adjusted,
            rationale=f"Adjusted for obsolescence ({from_decimal(inv_factor * 100):.0f}% of book)"
        ))
        
        # 4. Equipment and PP&E
        # Estimate as residual of assets minus known components
        known_current = cash + ar + inventory
        ppe_estimated = max(total_assets_book - known_current, Decimal("0"))
        ppe_factor = (
            equipment_fmv_factor
            if equipment_fmv_factor is not None
            else adjustments["equipment_markup"]
        )
        ppe_adjusted = ppe_estimated * ppe_factor
        adjusted_total += ppe_adjusted
        asset_adjustments.append(AssetAdjustment(
            asset_type="Property, Plant & Equipment",
            book_value=ppe_estimated,
            adjustment_factor=ppe_factor,
            adjusted_value=ppe_adjusted,
            rationale=f"Fair market value adjustment ({from_decimal(ppe_factor * 100):.0f}% of book)"
        ))
        
        # 5. Real Estate (if separately valued)
        if real_estate_fmv:
            adjusted_total += real_estate_fmv
            asset_adjustments.append(AssetAdjustment(
                asset_type="Real Estate",
                book_value=Decimal("0"),  # Assumed in PPE above
                adjustment_factor=Decimal("1.0"),
                adjusted_value=real_estate_fmv,
                rationale="Appraised Fair Market Value"
            ))
        
        # 6. Intangibles
        intangible = intangible_value or Decimal("0")
        if intangible > Decimal("0"):
            adjusted_total += intangible
            asset_adjustments.append(AssetAdjustment(
                asset_type="Intangible Assets",
                book_value=Decimal("0"),
                adjustment_factor=Decimal("1.0"),
                adjusted_value=intangible,
                rationale="Customer lists, brand value, patents, etc."
            ))
        
        # 7. Other revaluations (participations, machinery, vehicles, etc.)
        other_reval = other_revaluations or Decimal("0")
        if other_reval != Decimal("0"):
            adjusted_total += other_reval
            asset_adjustments.append(AssetAdjustment(
                asset_type="Other Revaluations",
                book_value=Decimal("0"),
                adjustment_factor=Decimal("1.0"),
                adjusted_value=other_reval,
                rationale="Participations, machinery, vehicles, and other asset revaluations"
            ))
        
        # Liabilities (typically at book value)
        liabilities_adjusted = total_liabilities_book
        
        # Net Asset Value
        net_asset_value = adjusted_total - liabilities_adjusted
        
        # Tangible vs Intangible split
        tangible_value = net_asset_value - intangible
        
        # Calculate range (±10%)
        value_low = net_asset_value * Decimal("0.90")
        value_high = net_asset_value * Decimal("1.10")
        
        # Determine confidence
        confidence = ConfidenceLevel.MEDIUM
        if year_data.total_assets is not None and year_data.total_liabilities is not None:
            confidence = ConfidenceLevel.HIGH
        if len(warnings) > 0:
            confidence = ConfidenceLevel.LOW
        
        result = AssetBasedResult(
            method=AssetValuationMethod.ADJUSTED_BOOK_VALUE,
            total_assets_book=total_assets_book,
            total_liabilities_book=total_liabilities_book,
            net_book_value=total_assets_book - total_liabilities_book,
            total_assets_adjusted=adjusted_total,
            total_liabilities_adjusted=liabilities_adjusted,
            net_asset_value=bank_round(net_asset_value),
            asset_adjustments=asset_adjustments,
            tangible_asset_value=bank_round(tangible_value),
            intangible_asset_value=intangible,
            value_low=bank_round(value_low),
            value_high=bank_round(value_high),
            confidence=confidence,
            methodology="Asset-Based (Adjusted Book Value)",
            sources=[
                "Hitchner (2017) Financial Valuation Ch. 8",
                "Pratt & Niculita (2008) Valuing a Business",
                "USPAP Standards 9-10",
            ],
            rationale=f"Adjusted book value for {industry} business with {len(asset_adjustments)} asset categories adjusted to FMV",
            warnings=warnings,
            industry=industry,
        )
        
        logger.info(
            f"Adjusted Book Value calculated",
            book_value=from_decimal(total_assets_book - total_liabilities_book),
            adjusted_value=from_decimal(net_asset_value),
            adjustments_count=len(asset_adjustments),
            confidence=confidence.value,
        )
        
        return result
    
    def calculate_liquidation_value(
        self,
        orderly: bool = True,
        industry: str = "other",
    ) -> AssetBasedResult:
        """
        Calculate Liquidation Value.
        
        Args:
            orderly: True for orderly (6-12 months), False for forced (immediate)
            industry: Industry for context
            
        Returns:
            AssetBasedResult with liquidation values
        """
        year_data = self.current_year
        method = "orderly" if orderly else "forced"
        factors = LIQUIDATION_FACTORS[method]
        
        asset_adjustments = []
        warnings = []
        
        # Get book values
        total_assets_book = (
            year_data.total_assets if year_data.total_assets is not None else Decimal("0")
        )
        total_liabilities_book = (
            year_data.total_liabilities
            if year_data.total_liabilities is not None
            else Decimal("0")
        )
        
        if total_assets_book <= Decimal("0"):
            warnings.append("Total assets not provided - using estimated values")
            total_assets_book = year_data.revenue / Decimal("1.5")
        
        adjusted_total = Decimal("0")
        
        # Apply liquidation factors to each asset class
        cash = year_data.cash if year_data.cash is not None else Decimal("0")
        cash_adj = cash * factors["cash"]
        adjusted_total += cash_adj
        asset_adjustments.append(AssetAdjustment(
            asset_type="Cash",
            book_value=cash,
            adjustment_factor=factors["cash"],
            adjusted_value=cash_adj,
            rationale="Cash at face value"
        ))
        
        ar = (
            year_data.accounts_receivable
            if year_data.accounts_receivable is not None
            else total_assets_book * Decimal("0.20")
        )
        ar_adj = ar * factors["accounts_receivable"]
        adjusted_total += ar_adj
        asset_adjustments.append(AssetAdjustment(
            asset_type="Accounts Receivable",
            book_value=ar,
            adjustment_factor=factors["accounts_receivable"],
            adjusted_value=ar_adj,
            rationale=f"{'Orderly' if orderly else 'Forced'} collection value"
        ))
        
        inventory = (
            year_data.inventory
            if year_data.inventory is not None
            else total_assets_book * Decimal("0.15")
        )
        inv_adj = inventory * factors["inventory"]
        adjusted_total += inv_adj
        asset_adjustments.append(AssetAdjustment(
            asset_type="Inventory",
            book_value=inventory,
            adjustment_factor=factors["inventory"],
            adjusted_value=inv_adj,
            rationale=f"{'Orderly' if orderly else 'Forced'} liquidation sale"
        ))
        
        # Equipment/PP&E
        known_current = cash + ar + inventory
        ppe = max(total_assets_book - known_current, Decimal("0"))
        ppe_adj = ppe * factors["equipment"]
        adjusted_total += ppe_adj
        asset_adjustments.append(AssetAdjustment(
            asset_type="Equipment & PP&E",
            book_value=ppe,
            adjustment_factor=factors["equipment"],
            adjusted_value=ppe_adj,
            rationale=f"{'Orderly' if orderly else 'Auction'} equipment sale"
        ))
        
        # Liabilities remain at book value
        liabilities_adjusted = total_liabilities_book
        
        # Add liquidation costs (typically 5-10% of assets)
        liquidation_costs = adjusted_total * Decimal("0.05" if orderly else "0.10")
        liabilities_adjusted += liquidation_costs
        warnings.append(f"Liquidation costs estimated at {from_decimal(liquidation_costs):,.0f}")
        
        net_value = adjusted_total - liabilities_adjusted
        net_value = max(net_value, Decimal("0"))  # Can't be negative
        
        result = AssetBasedResult(
            method=AssetValuationMethod.ORDERLY_LIQUIDATION if orderly else AssetValuationMethod.FORCED_LIQUIDATION,
            total_assets_book=total_assets_book,
            total_liabilities_book=total_liabilities_book,
            net_book_value=total_assets_book - total_liabilities_book,
            total_assets_adjusted=adjusted_total,
            total_liabilities_adjusted=liabilities_adjusted,
            net_asset_value=bank_round(net_value),
            asset_adjustments=asset_adjustments,
            tangible_asset_value=bank_round(net_value),
            intangible_asset_value=Decimal("0"),  # Intangibles worthless in liquidation
            value_low=bank_round(net_value * Decimal("0.85")),
            value_high=bank_round(net_value * Decimal("1.15")),
            confidence=ConfidenceLevel.MEDIUM,
            methodology=f"Asset-Based ({'Orderly' if orderly else 'Forced'} Liquidation)",
            sources=[
                "Pratt & Niculita (2008) Valuing a Business",
                "Hitchner (2017) Financial Valuation",
            ],
            rationale=f"{'Orderly' if orderly else 'Forced'} liquidation value based on industry recovery rates",
            warnings=warnings,
            industry=industry,
        )
        
        logger.info(
            f"{'Orderly' if orderly else 'Forced'} Liquidation Value calculated",
            book_value=from_decimal(total_assets_book - total_liabilities_book),
            liquidation_value=from_decimal(net_value),
        )
        
        return result
    
    def is_asset_based_appropriate(self) -> Tuple[bool, str]:
        """
        Determine if asset-based valuation is appropriate.
        
        Returns:
            Tuple of (is_appropriate, reason)
        """
        year_data = self.current_year
        
        # Check if EBITDA is negative (going concern doubt)
        if year_data.ebitda <= Decimal("0"):
            return True, "Negative EBITDA - asset-based provides floor value"
        
        # Check if assets are significant relative to revenue
        if year_data.total_assets and year_data.revenue > 0:
            asset_to_revenue = year_data.total_assets / year_data.revenue
            if asset_to_revenue > Decimal("1.5"):
                return True, f"High asset intensity ({from_decimal(asset_to_revenue):.1f}x revenue) - asset-based is relevant"
        
        # Check profitability
        ebitda_margin = year_data.ebitda / year_data.revenue if year_data.revenue > 0 else Decimal("0")
        if ebitda_margin < Decimal("0.05"):  # Less than 5% margin
            return True, "Low profitability - asset-based provides alternative perspective"
        
        return False, "Income-based methods more appropriate for this business profile"


# ============================================================================
# Factory Function
# ============================================================================

def create_asset_based_engine(
    financial_data: FinancialData,
    country_code: str = "BE",
) -> AssetBasedEngine:
    """
    Factory function to create Asset-Based Engine.
    
    Args:
        financial_data: Company financial data
        country_code: ISO country code
        
    Returns:
        Configured AssetBasedEngine instance
    """
    return AssetBasedEngine(financial_data=financial_data, country_code=country_code)
