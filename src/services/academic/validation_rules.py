"""
Academic Validation Rules Registry

Defines validation rules for each valuation methodology based on academic standards.

Rules are based on:
- Damodaran (2012, 2018): Investment Valuation
- Koller et al. (2020): Valuation - Measuring and Managing Value
- McKinsey Valuation Handbook (2020)
- Ibbotson SBBI Yearbook (2024)
- Duff & Phelps Valuation Handbook (2024)
- Big 4 Guidelines (PwC, Deloitte, EY, KPMG)

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict, List
from src.services.academic.models import ValidationRule, ConfidenceLevel


class ValidationRulesRegistry:
    """Registry of academic validation rules for valuation calculations"""
    
    # EBITDA Multiples Rules
    EBITDA_MULTIPLE_RANGE = ValidationRule(
        rule_id="ebitda_multiple_range",
        rule_name="EBITDA Multiple Range",
        rule_type="range",
        min_value=Decimal("2.0"),
        max_value=Decimal("15.0"),
        academic_source_ids=["damodaran_2012", "ibbotson_2024", "koller_2020"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="EBITDA multiple outside typical range (2.0x - 15.0x). Per Damodaran (2012) and industry data.",
        warning_message="EBITDA multiple at extreme end of range. Verify industry comparables."
    )
    
    EBITDA_MULTIPLE_SME_RANGE = ValidationRule(
        rule_id="ebitda_multiple_sme_range",
        rule_name="EBITDA Multiple SME Range",
        rule_type="range",
        min_value=Decimal("3.0"),
        max_value=Decimal("12.0"),
        academic_source_ids=["ibbotson_2024", "pwc_2024", "bdo_multiples"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="EBITDA multiple for SMEs typically ranges 3.0x - 12.0x per IBISWorld and transaction data.",
        warning_message="EBITDA multiple approaching extreme for SME market."
    )
    
    # Size Discount Rules
    SIZE_DISCOUNT_RANGE = ValidationRule(
        rule_id="size_discount_range",
        rule_name="Size Discount Range",
        rule_type="range",
        min_value=Decimal("0.10"),  # 10%
        max_value=Decimal("0.40"),  # 40%
        academic_source_ids=["ibbotson_2024", "duff_phelps_2024", "fama_french_1992"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="Size discount outside empirical range (10% - 40%). Per Ibbotson SBBI and Duff & Phelps research.",
        warning_message="Size discount at extreme end. Verify company size tier."
    )
    
    SIZE_DISCOUNT_SMALL_SME = ValidationRule(
        rule_id="size_discount_small_sme",
        rule_name="Size Discount Small SME",
        rule_type="range",
        min_value=Decimal("0.25"),  # 25%
        max_value=Decimal("0.35"),  # 35%
        academic_source_ids=["ibbotson_2024", "duff_phelps_2024"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="Size discount for small SMEs (<€5M revenue) typically 25-35% per Ibbotson SBBI.",
        warning_message="Size discount for small SME outside typical range."
    )
    
    # Owner Dependency / Key Person Risk Rules
    OWNER_DEPENDENCY_DISCOUNT_RANGE = ValidationRule(
        rule_id="owner_dependency_discount_range",
        rule_name="Owner Dependency Discount Range",
        rule_type="range",
        min_value=Decimal("0.05"),  # 5%
        max_value=Decimal("0.40"),  # 40%
        academic_source_ids=["mckinsey_2020", "pwc_2024", "damodaran_2012"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="Owner dependency discount outside typical range (5% - 40%). Per McKinsey and Big 4 guidelines.",
        warning_message="Owner dependency discount at extreme. Verify scoring."
    )
    
    # Liquidity Discount Rules
    LIQUIDITY_DISCOUNT_RANGE = ValidationRule(
        rule_id="liquidity_discount_range",
        rule_name="Liquidity Discount Range",
        rule_type="range",
        min_value=Decimal("0.20"),  # 20%
        max_value=Decimal("0.40"),  # 40%
        academic_source_ids=["longstaff_1995", "silber_1991", "pwc_2024"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="Liquidity discount outside empirical range (20% - 40%). Per Longstaff (1995) and Silber (1991).",
        warning_message="Liquidity discount should typically not apply to SME multiples (already illiquid)."
    )
    
    # Customer Concentration Rules
    CUSTOMER_CONCENTRATION_DISCOUNT_RANGE = ValidationRule(
        rule_id="customer_concentration_discount_range",
        rule_name="Customer Concentration Discount Range",
        rule_type="range",
        min_value=Decimal("0.05"),  # 5%
        max_value=Decimal("0.30"),  # 30%
        academic_source_ids=["mckinsey_2020", "pwc_2024"],
        confidence_level=ConfidenceLevel.MEDIUM_HIGH,
        error_message="Customer concentration discount outside typical range (5% - 30%). Per Big 4 practice.",
        warning_message="Customer concentration discount significant. Verify concentration metrics."
    )
    
    # DCF Rules
    DCF_TERMINAL_GROWTH_RATE = ValidationRule(
        rule_id="dcf_terminal_growth_rate",
        rule_name="DCF Terminal Growth Rate",
        rule_type="range",
        min_value=Decimal("0.015"),  # 1.5%
        max_value=Decimal("0.045"),  # 4.5%
        academic_source_ids=["koller_2020", "damodaran_2018", "mckinsey_2020"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="Terminal growth rate outside reasonable range (1.5% - 4.5%). Per Koller et al. and economic theory.",
        warning_message="Terminal growth rate should not exceed long-term GDP growth."
    )
    
    DCF_WACC_RANGE = ValidationRule(
        rule_id="dcf_wacc_range",
        rule_name="DCF WACC Range",
        rule_type="range",
        min_value=Decimal("0.08"),  # 8%
        max_value=Decimal("0.25"),  # 25%
        academic_source_ids=["damodaran_2012", "koller_2020", "ibbotson_2024"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="WACC outside typical range (8% - 25%). Verify cost of capital calculation.",
        warning_message="WACC at extreme. Review risk-free rate, beta, and market risk premium."
    )
    
    DCF_BETA_RANGE = ValidationRule(
        rule_id="dcf_beta_range",
        rule_name="DCF Beta Range",
        rule_type="range",
        min_value=Decimal("0.5"),
        max_value=Decimal("2.0"),
        academic_source_ids=["fama_french_1992", "damodaran_2012"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="Beta outside typical range (0.5 - 2.0). Verify industry beta and leverage adjustment.",
        warning_message="Beta at extreme. Most SMEs have betas between 0.8 and 1.5."
    )
    
    # Revenue Multiple Rules
    REVENUE_MULTIPLE_RANGE = ValidationRule(
        rule_id="revenue_multiple_range",
        rule_name="Revenue Multiple Range",
        rule_type="range",
        min_value=Decimal("0.3"),
        max_value=Decimal("10.0"),
        academic_source_ids=["damodaran_2018", "ibbotson_2024"],
        confidence_level=ConfidenceLevel.MEDIUM_HIGH,
        error_message="Revenue multiple outside typical range (0.3x - 10.0x). Highly variable by industry.",
        warning_message="Revenue multiples vary significantly by industry. Verify comparables."
    )
    
    REVENUE_MULTIPLE_SAAS_RANGE = ValidationRule(
        rule_id="revenue_multiple_saas_range",
        rule_name="Revenue Multiple SaaS Range",
        rule_type="range",
        min_value=Decimal("2.0"),
        max_value=Decimal("15.0"),
        academic_source_ids=["saas_capital_index", "damodaran_2018"],
        confidence_level=ConfidenceLevel.MEDIUM_HIGH,
        error_message="SaaS revenue multiple outside typical range (2.0x - 15.0x). Depends heavily on growth and retention.",
        warning_message="SaaS multiples highly sensitive to growth rate and churn. Verify metrics."
    )
    
    # Range Width Rules
    VALUATION_RANGE_WIDTH = ValidationRule(
        rule_id="valuation_range_width",
        rule_name="Valuation Range Width",
        rule_type="range",
        min_value=Decimal("0.15"),  # 15%
        max_value=Decimal("0.50"),  # 50%
        academic_source_ids=["mckinsey_2020", "damodaran_2012"],
        confidence_level=ConfidenceLevel.MEDIUM_HIGH,
        error_message="Valuation range width outside typical bounds (15% - 50% around midpoint).",
        warning_message="Wide valuation range indicates higher uncertainty. Review data quality."
    )
    
    # Confidence Score Rules
    CONFIDENCE_SCORE_RANGE = ValidationRule(
        rule_id="confidence_score_range",
        rule_name="Confidence Score Range",
        rule_type="range",
        min_value=Decimal("0.0"),
        max_value=Decimal("1.0"),
        academic_source_ids=["pwc_2024"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="Confidence score must be between 0.0 and 1.0.",
        warning_message="Low confidence score (<0.6) indicates significant valuation uncertainty."
    )
    
    # === SME-SPECIFIC VALIDATION RULES ===
    
    # Private Company Discount (SME)
    SME_PRIVATE_COMPANY_DISCOUNT = ValidationRule(
        rule_id="sme_private_company_discount",
        rule_name="SME Private Company Discount",
        rule_type="range",
        min_value=Decimal("0.15"),  # 15%
        max_value=Decimal("0.35"),  # 35%
        academic_source_ids=["koeplin_2000", "officer_2007", "trugman_2017"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="SME private company discount typically 15-35% per Koeplin et al. (2000) and Officer (2007).",
        warning_message="Private company discount should reflect lack of marketability for SMEs."
    )
    
    # SME Marketability Discount
    SME_MARKETABILITY_DISCOUNT = ValidationRule(
        rule_id="sme_marketability_discount",
        rule_name="SME Marketability Discount",
        rule_type="range",
        min_value=Decimal("0.20"),  # 20%
        max_value=Decimal("0.50"),  # 50%
        academic_source_ids=["emory_2002", "hitchner_2017", "trugman_2017"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="SME marketability discount typically 20-50% per Emory (2002) pre-IPO studies.",
        warning_message="Marketability discount for SMEs higher than public companies due to limited buyer pool."
    )
    
    # SME WACC Range (Higher than large companies)
    SME_WACC_RANGE = ValidationRule(
        rule_id="sme_wacc_range",
        rule_name="SME WACC Range",
        rule_type="range",
        min_value=Decimal("0.12"),  # 12%
        max_value=Decimal("0.25"),  # 25%
        academic_source_ids=["trugman_2017", "duff_phelps_2024", "coulon_2021"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="SME WACC typically 12-25%, higher than large companies due to size premium and risk.",
        warning_message="SME cost of capital should reflect size premium and illiquidity premium."
    )
    
    # SME Owner Compensation Normalization
    SME_OWNER_COMP_ADJUSTMENT = ValidationRule(
        rule_id="sme_owner_comp_adjustment",
        rule_name="SME Owner Compensation Adjustment",
        rule_type="range",
        min_value=Decimal("-0.30"),  # -30% (owner underpaid)
        max_value=Decimal("0.50"),   # +50% (owner overpaid)
        academic_source_ids=["trugman_2017", "hitchner_2017", "pratt_niculita_2008"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="Owner compensation adjustment outside typical range (-30% to +50%). Normalize to market rates.",
        warning_message="SME owner compensation often deviates from market. Adjust EBITDA for normalization."
    )
    
    # SME Revenue Size (for classification)
    SME_REVENUE_MICRO = ValidationRule(
        rule_id="sme_revenue_micro",
        rule_name="Micro SME Revenue Range",
        rule_type="range",
        min_value=Decimal("0"),
        max_value=Decimal("500000"),  # €500K
        academic_source_ids=["european_commission_2023", "coulon_2021"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="Micro SME defined as <€500K revenue per EU classification.",
        warning_message="Micro SMEs require specialized valuation approaches (asset-based, excess earnings)."
    )
    
    SME_REVENUE_SMALL = ValidationRule(
        rule_id="sme_revenue_small",
        rule_name="Small SME Revenue Range",
        rule_type="range",
        min_value=Decimal("500000"),    # €500K
        max_value=Decimal("5000000"),   # €5M
        academic_source_ids=["european_commission_2023", "coulon_2021", "trugman_2017"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="Small SME defined as €500K-€5M revenue per EU and AICPA standards.",
        warning_message="Small SMEs typically valued using multiples or capitalized earnings methods."
    )
    
    SME_REVENUE_MEDIUM = ValidationRule(
        rule_id="sme_revenue_medium",
        rule_name="Medium SME Revenue Range",
        rule_type="range",
        min_value=Decimal("5000000"),   # €5M
        max_value=Decimal("50000000"),  # €50M
        academic_source_ids=["european_commission_2023", "coulon_2021"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="Medium SME defined as €5M-€50M revenue per EU classification.",
        warning_message="Medium SMEs suitable for DCF, multiples, or hybrid approaches."
    )
    
    # Belgian/European SME Multiples
    BELGIAN_SME_EBITDA_MULTIPLE = ValidationRule(
        rule_id="belgian_sme_ebitda_multiple",
        rule_name="Belgian SME EBITDA Multiple Range",
        rule_type="range",
        min_value=Decimal("4.0"),
        max_value=Decimal("8.0"),
        academic_source_ids=["vfb_belgium_2024", "vlerick_2023", "bdo_multiples"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="Belgian SME EBITDA multiples typically 4.0x-8.0x per VFB and Vlerick research.",
        warning_message="Belgian market multiples tend to be more conservative than US/UK markets."
    )
    
    # Family Business Discount (common in European SMEs)
    FAMILY_BUSINESS_CONTROL_DISCOUNT = ValidationRule(
        rule_id="family_business_control_discount",
        rule_name="Family Business Minority Discount",
        rule_type="range",
        min_value=Decimal("0.15"),  # 15%
        max_value=Decimal("0.35"),  # 35%
        academic_source_ids=["uclouvain_2022", "coulon_2021", "astrachan_2003"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="Family business minority discount typically 15-35% per European research.",
        warning_message="Family-controlled SMEs may require minority interest discount for non-controlling stakes."
    )
    
    # SME Information Asymmetry Discount
    SME_INFORMATION_ASYMMETRY_DISCOUNT = ValidationRule(
        rule_id="sme_information_asymmetry_discount",
        rule_name="SME Information Asymmetry Discount",
        rule_type="range",
        min_value=Decimal("0.05"),  # 5%
        max_value=Decimal("0.20"),  # 20%
        academic_source_ids=["astrachan_2003", "petersen_2004", "officer_2007"],
        confidence_level=ConfidenceLevel.MEDIUM_HIGH,
        error_message="SME information asymmetry discount typically 5-20% for limited financial transparency.",
        warning_message="SMEs with poor financial reporting quality may require additional discount."
    )
    
    # SME Transaction Database Ranges
    SME_TRANSACTION_EBITDA_MULTIPLE = ValidationRule(
        rule_id="sme_transaction_ebitda_multiple",
        rule_name="SME Transaction EBITDA Multiple (Database)",
        rule_type="range",
        min_value=Decimal("3.5"),
        max_value=Decimal("7.5"),
        academic_source_ids=["pepperdine_2024", "bizcomps_2024", "done_deals_2024"],
        confidence_level=ConfidenceLevel.VERY_HIGH,
        error_message="SME transaction EBITDA multiples typically 3.5x-7.5x per Pepperdine and BizComps databases.",
        warning_message="Actual transaction multiples for SMEs lower than public company multiples."
    )
    
    SME_TRANSACTION_REVENUE_MULTIPLE = ValidationRule(
        rule_id="sme_transaction_revenue_multiple",
        rule_name="SME Transaction Revenue Multiple (Database)",
        rule_type="range",
        min_value=Decimal("0.4"),
        max_value=Decimal("2.5"),
        academic_source_ids=["pepperdine_2024", "bizcomps_2024"],
        confidence_level=ConfidenceLevel.HIGH,
        error_message="SME transaction revenue multiples typically 0.4x-2.5x per transaction databases.",
        warning_message="Revenue multiples for SMEs highly variable by industry and profitability."
    )
    
    @classmethod
    def get_all_rules(cls) -> List[ValidationRule]:
        """Get all validation rules"""
        return [
            getattr(cls, attr) for attr in dir(cls)
            if isinstance(getattr(cls, attr), ValidationRule)
        ]
    
    @classmethod
    def get_rules_by_category(cls, category: str) -> List[ValidationRule]:
        """
        Get validation rules for a specific category
        
        Args:
            category: Category name (ebitda, dcf, discount, etc.)
            
        Returns:
            List of relevant validation rules
        """
        all_rules = cls.get_all_rules()
        category_lower = category.lower()
        
        return [
            rule for rule in all_rules
            if category_lower in rule.rule_id.lower()
        ]
    
    @classmethod
    def get_rule_by_id(cls, rule_id: str) -> ValidationRule:
        """
        Get specific validation rule by ID
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            ValidationRule or None if not found
        """
        for attr in dir(cls):
            rule = getattr(cls, attr)
            if isinstance(rule, ValidationRule) and rule.rule_id == rule_id:
                return rule
        return None


# Create global registry instance
VALIDATION_RULES_REGISTRY = ValidationRulesRegistry()

