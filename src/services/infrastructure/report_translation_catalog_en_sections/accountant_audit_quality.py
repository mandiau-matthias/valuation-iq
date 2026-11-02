"""Accountant audit, source, quality, roadmap, and business-type copy."""

from __future__ import annotations


def build_english_accountant_audit_quality_translations() -> dict[str, object]:
    return {
        # Phase 2: Audit Trail
        "accountant_audit_section_title": "Appendix E — Calculation Methodology & Algorithmic Audit Trail",
        "accountant_audit_verification_badge": "Methodology Verification",
        "accountant_audit_intro": (
            "This appendix provides the complete algorithmic audit trail demonstrating "
            "<strong>Primitive 2: Algorithmic Defensibility</strong> - a systematic, step-by-step "
            "reconstruction of the valuation methodology. Every calculation step, adjustment "
            "factor, and analytical decision is documented to ensure full reproducibility and "
            "compliance with <strong>USPAP Standard 9 (Development Requirements)</strong> for "
            "professional defensibility."
        ),
        "accountant_audit_documentation_label": "Professional Documentation Standard:",
        "accountant_audit_documentation_body": (
            "USPAP Standard 9 requires comprehensive documentation of the valuation process, "
            "including all assumptions, data sources, and analytical methodologies. This audit "
            "trail enables independent peer review, regulatory compliance verification, and "
            "stakeholder understanding of the valuation foundation, supporting the fiduciary "
            "standard required for institutional transactions."
        ),
        "accountant_audit_table_title": "Calculation Methodology Audit Trail",
        "accountant_audit_table_intro": (
            "The following table documents each step in the valuation process, providing the "
            "rationale, data sources, and methodological decisions that led to the final "
            "valuation conclusion. This transparency ensures institutional stakeholders can "
            "independently verify the analysis."
        ),
        "accountant_audit_caption": "Valuation Process Audit Trail - Complete Methodological Documentation",
        "accountant_audit_col_step": "Step",
        "accountant_audit_col_process": "Process Component",
        "accountant_audit_col_rationale": "Methodological Rationale",
        "accountant_audit_col_source": "Data Source",
        "accountant_audit_col_status": "Status",
        "accountant_audit_step_prefix": "Step",
        "accountant_audit_calc_step_default": "Calculation step performed",
        "accountant_audit_reference_label": "Reference:",
        "accountant_audit_internal_calc": "Internal calculation",
        "accountant_audit_step1_name": "Data Quality Assessment",
        "accountant_audit_step1_rationale": (
            "Comprehensive evaluation of financial data integrity, completeness, and reliability. "
            "Quality metrics calculated for confidence scoring and valuation adjustments."
        ),
        "accountant_audit_step1_ref": "Reference: ASA BVS-III, Data Quality Standards",
        "accountant_audit_step1_source": "Financial statements & metadata",
        "accountant_audit_step2_name": "Input Data & Business Profile",
        "accountant_audit_step2_rationale": (
            "Business profile validation and financial data ingestion. Company characteristics, "
            "industry classification, and operational metrics established for valuation framework."
        ),
        "accountant_audit_step2_ref": "Reference: IVS 105, Business Description Standards",
        "accountant_audit_step2_source": "User input & registry data",
        "accountant_audit_step3_name": "Industry Benchmarking & Multiple Selection",
        "accountant_audit_step3_rationale": (
            "Market-based valuation multiples selected through industry benchmarking. Comparable "
            "company analysis with size, growth, and risk adjustments applied to establish "
            "baseline multiples."
        ),
        "accountant_audit_step3_ref": "Reference: VFB Belgium 2024, Trugman (2017)",
        "accountant_audit_step3_source": "Business type database",
        "accountant_audit_step4_name": "Base Enterprise Value Calculation",
        "accountant_audit_step4_rationale": (
            "Base enterprise value calculated using selected multiples and normalized EBITDA. "
            "Quality calibration applied to multiple (Step 2.5). Multiple adjusted from comparable "
            "base to company-specific calibrated multiple."
        ),
        "accountant_audit_step4_ref": "Reference: AICPA BVS-VII, Multiple-First Methodology",
        "accountant_audit_step4_source": "Calculated from Step 2 & normalized financials",
        "accountant_audit_step5_name": "Owner Concentration Adjustment",
        "accountant_audit_step5_rationale": (
            "Owner/employee ratio analysis for key person risk assessment. Ratio of 33% indicates "
            "LOW key person risk. Owners represent &lt;10% of the workforce, indicating deep "
            "management bench and operational independence."
        ),
        "accountant_audit_step5_ref": "Reference: Damodaran (2012), Key Person Risk Framework",
        "accountant_audit_step5_source": "Employee count & ownership data",
        "accountant_audit_step6_name": "Size Discount Application",
        "accountant_audit_step6_rationale": (
            "Company size adjustment applied to valuation multiple. Size premium/discount "
            "calculated based on revenue scale relative to market comparables and liquidity "
            "considerations."
        ),
        "accountant_audit_step6_ref": "Reference: Ibbotson SBBI (2024), Size Effect Research",
        "accountant_audit_step6_source": "Revenue data & size benchmarks",
        "accountant_audit_step7_name": "Liquidity Discount Application",
        "accountant_audit_step7_rationale": (
            "Private company illiquidity discount applied to valuation multiple. DLOM calculated "
            "based on company size, growth profile, and marketability factors."
        ),
        "accountant_audit_step7_ref": "Reference: Koeplin (2000), Officer (2007), DLOM Framework",
        "accountant_audit_step7_source": "Marketability & size analysis",
        "accountant_audit_step8_name": "Enterprise Value to Equity Conversion",
        "accountant_audit_step8_rationale": (
            "Enterprise value converted to equity value through debt adjustment (EV - Net Debt). "
            "Ensures valuation represents actual shareholder value."
        ),
        "accountant_audit_step8_ref": "Reference: USPAP Standards, Equity Value Framework",
        "accountant_audit_step8_source": "Balance sheet data",
        "accountant_audit_step9_name": "Confidence Score Analysis",
        "accountant_audit_step9_rationale": (
            "Overall valuation confidence score calculated based on data quality, methodology "
            "robustness, and market comparability. Range methodology determined accordingly."
        ),
        "accountant_audit_step9_ref": "Reference: AICPA BVS-VII, Confidence Intervals",
        "accountant_audit_step9_source": "Quality assessment & methodology analysis",
        "accountant_audit_step10_name": "Range Methodology & Final Synthesis",
        "accountant_audit_step10_rationale": (
            "Final valuation range synthesized using multiple dispersion methodology. "
            "Multiple-first approach ensures no double-counting of risk adjustments across "
            "valuation components."
        ),
        "accountant_audit_step10_ref": "Reference: USPAP Standards, Range Methodology Framework",
        "accountant_audit_step10_source": "Integrated calculation results",
        "accountant_audit_steps_label": "Steps 10-11",
        "accountant_audit_step_zero": "Step 0",
        "accountant_audit_step_one": "Step 1",
        "accountant_audit_step_two": "Step 2",
        "accountant_audit_step_three": "Step 3",
        "accountant_audit_step_four": "Step 4",
        "accountant_audit_step_five": "Step 5",
        "accountant_audit_step_six": "Step 6",
        "accountant_audit_step_seven": "Step 7",
        "accountant_audit_step_nine": "Step 9",
        "accountant_audit_methodology_summary_title": "Methodology Integrity Verification",
        "accountant_audit_primary_approach_title": "Primary Approach",
        "accountant_audit_primary_approach_body": (
            "<strong>Market Approach (Multiples):</strong> Primary methodology selected due to "
            "high data availability and market comparability for SME valuation."
        ),
        "accountant_audit_dcf_exclusion_title": "DCF Exclusion",
        "accountant_audit_dcf_exclusion_body": (
            "<strong>Revenue below €1M:</strong> Income approach excluded due to small firm "
            "effect and forecasting uncertainty in sub-€1M revenue companies."
        ),
        "accountant_audit_risk_adjustments_title": "Risk Adjustments",
        "accountant_audit_risk_adjustments_body": (
            "<strong>Multiple-First Discounting:</strong> All risk adjustments applied to "
            "valuation multiple rather than earnings, preventing double-counting and ensuring "
            "mathematical defensibility."
        ),
        "accountant_audit_primitive_standards_title": "Primitive 2: Algorithmic Defensibility Standards",
        "accountant_audit_primitive_standards_body": (
            "<strong>USPAP Compliance:</strong> This audit trail demonstrates complete "
            "methodological transparency required for professional valuation standards. Each step "
            "includes data sources, calculation rationale, and academic references to ensure "
            "reproducibility and regulatory compliance."
        ),
        # Phase 2: Information Sources
        "accountant_sources_section_title": "Appendix C — Information Sources & Data Reliability Assessment",
        "accountant_sources_transparency_badge": "Data Transparency",
        "accountant_sources_intro": (
            "This appendix provides comprehensive documentation of all data sources, "
            "methodologies, and reliability assessments employed in the valuation analysis. In "
            "accordance with <strong>USPAP Standard 9 (Documentation Requirements)</strong> and "
            "<strong>IVS 105</strong>, all information sources are systematically documented with "
            "reliability ratings to ensure methodological transparency and professional "
            "defensibility."
        ),
        "accountant_sources_disclosure_label": "Professional Disclosure Standard:",
        "accountant_sources_disclosure_body": (
            "Valuation reliability is fundamentally anchored in data quality. This appendix "
            "enables stakeholders to independently assess the robustness of the analytical "
            "foundation and adjust confidence levels based on source reliability. Reliability "
            "ratings follow <strong>AICPA BVS-VII</strong> standards for SME valuation data "
            "assessment."
        ),
        "accountant_sources_inventory_title": "Data Source Inventory",
        "accountant_sources_inventory_intro": (
            "The following table inventories all primary data sources utilized in this valuation, "
            "including their descriptions, applications, and assessed reliability levels. "
            "Reliability ratings follow AICPA BVS-VII standards for SME valuation data "
            "assessment."
        ),
        "accountant_sources_caption": "Data Sources & Reliability Assessment",
        "accountant_sources_col_category": "Source Category",
        "accountant_sources_col_description": "Description & Application",
        "accountant_sources_col_reliability": "Reliability",
        "accountant_sources_col_impact": "Valuation Impact",
        "accountant_sources_primary_data": "Primary Data",
        "accountant_sources_benchmarking_data": "Benchmarking Data",
        "accountant_sources_supporting_data": "Supporting Data",
        "accountant_sources_used_for_financials": "Used for: Revenue, EBITDA, margin analysis, normalization adjustments",
        "accountant_sources_used_for_multiples": "Used for: Enterprise value multiples, industry benchmarking, size adjustments",
        "accountant_sources_reliability_high": "High",
        "accountant_sources_reliability_medium": "Medium",
        "accountant_sources_reliability_low": "Low",
        "accountant_sources_impact_high": "+10% confidence",
        "accountant_sources_impact_baseline": "Baseline",
        "accountant_sources_impact_low": "-15% confidence",
        "accountant_sources_quality_framework_title": "Data Quality Framework",
        "accountant_sources_reliability_ratings_title": "Reliability Ratings",
        "accountant_sources_rating_high": "<strong>High:</strong> Audited financials, recent transactions",
        "accountant_sources_rating_medium": "<strong>Medium:</strong> Management-prepared data, industry benchmarks",
        "accountant_sources_rating_low": "<strong>Low:</strong> Estimates, outdated information, limited verification",
        "accountant_sources_confidence_impact_title": "Confidence Impact",
        "accountant_sources_confidence_high": "<strong>+10%:</strong> High reliability strengthens valuation range",
        "accountant_sources_confidence_baseline": "<strong>Baseline:</strong> Medium reliability represents standard market practice",
        "accountant_sources_confidence_low": "<strong>-15%:</strong> Low reliability triggers wider valuation ranges",
        "accountant_sources_quality_controls_title": "Quality Controls",
        "accountant_sources_qc_cross": "<strong>Cross-validation:</strong> Multiple sources compared for consistency",
        "accountant_sources_qc_reasonableness": "<strong>Reasonableness tests:</strong> Data compared to industry norms",
        "accountant_sources_qc_documentation": "<strong>Documentation:</strong> All assumptions and limitations noted",
        "accountant_sources_fs_review_title": "Financial Statements Review",
        "accountant_sources_fs_review_intro": (
            "The following financial statements were reviewed and utilized in the valuation "
            "analysis. All data has been assessed for completeness, internal consistency, and "
            "reasonableness."
        ),
        "accountant_sources_fs_reviewed_label": "Financials Reviewed",
        "accountant_sources_fs_review_date": "Review Date:",
        "accountant_sources_fs_assessment": "Assessment: Medium Reliability (Management-Prepared)",
        "accountant_sources_market_data_title": "Market Data Sources & Academic Citations",
        "accountant_sources_market_data_intro": (
            "Market multiples and benchmarking data are sourced from authoritative academic and "
            "industry publications. All sources include publication dates and methodological "
            "frameworks for transparency."
        ),
        "accountant_sources_col_source": "Source",
        "accountant_sources_col_publication": "Publication",
        "accountant_sources_col_application": "Application",
        "accountant_sources_uspap_compliance_title": "USPAP Standards Compliance",
        "accountant_sources_uspap_compliance_body": (
            "<strong>IVS 105 & USPAP:</strong> This disclosure ensures complete transparency "
            "regarding data sources and their reliability. Users can assess the appropriateness "
            "of the valuation conclusion based on the quality and nature of underlying "
            "information. All sources are current as of the valuation date and follow "
            "professional valuation standards for data documentation."
        ),
        "accountant_sources_app_damodaran": "Industry multiple selection, risk adjustments, market approach",
        "accountant_sources_app_koller": "Enterprise value methodology, GPCM framework",
        "accountant_sources_app_trugman": "SDE methodology, SME-specific adjustments, normalization",
        "accountant_sources_app_pratt": "Private company discounts, size premiums, lack of marketability",
        "accountant_sources_app_pepperdine": "SME size discounts, private company multiples calibration",
        "accountant_sources_app_vfb": "Belgian market multiples, industry-specific adjustments",
        "accountant_sources_app_vlerick": "Transaction-based multiples, SME valuation patterns",
        "accountant_sources_app_aicpa": "SDE standards, owner compensation normalization",
        "accountant_sources_app_ivs": "International valuation standards compliance",
        # Phase 2: Enhanced Normalization Schedule
        "accountant_norm_section_title": "Detailed Normalization Schedule (ASA BVS-III)",
        "accountant_norm_intro": (
            "The following schedule systematically identifies and quantifies adjustments required "
            "to convert tax-optimized financial statements into normalized economic earnings. "
            "Each category represents a standard normalization area per <strong>ASA BVS-III "
            "Quality of Earnings</strong> and <strong>Trugman (2017, Chapter 8)</strong> "
            "framework."
        ),
        "accountant_norm_caption": "Comprehensive Normalization Schedule",
        "accountant_norm_col_category": "Category",
        "accountant_norm_col_item": "Adjustment Item",
        "accountant_norm_col_amount": "Amount",
        "accountant_norm_col_rationale": "Rationale / Source",
        "accountant_norm_col_status": "Status",
        "accountant_norm_section_owner": "1. Owner Compensation Normalization",
        "accountant_norm_owner_salary": "Owner Salary Above/Below Market Rate",
        "accountant_norm_owner_salary_default": "Adjustment to market replacement salary",
        "accountant_norm_owner_salary_no": "Owner compensation at market rate (no adjustment required)",
        "accountant_norm_status_applied": "Applied",
        "accountant_norm_status_na": "N/A",
        "accountant_norm_section_discretionary": "2. Discretionary & Personal Expenses",
        "accountant_norm_personal_auto": "Personal Automobile Expenses",
        "accountant_norm_personal_auto_caption": "No personal vehicle expenses identified in operating costs",
        "accountant_norm_personal_travel": "Personal Travel & Entertainment",
        "accountant_norm_personal_travel_caption": "No discretionary travel expenses identified",
        "accountant_norm_family_comp": "Family Member Compensation (Non-Operational)",
        "accountant_norm_family_comp_caption": "No non-operational family compensation identified",
        "accountant_norm_personal_insurance": "Personal Insurance & Benefits",
        "accountant_norm_personal_insurance_caption": "No personal insurance expenses identified",
        "accountant_norm_section_nonrecurring": "3. Non-Recurring Items",
        "accountant_norm_litigation": "Litigation Settlements / Legal Costs",
        "accountant_norm_litigation_caption": "No one-time legal costs identified",
        "accountant_norm_restructuring": "Restructuring / Reorganization Costs",
        "accountant_norm_restructuring_caption": "No restructuring expenses identified",
        "accountant_norm_asset_sale": "Asset Sale Gains / Losses",
        "accountant_norm_asset_sale_caption": "No asset disposals in period",
        "accountant_norm_covid": "COVID-19 / Pandemic Relief Grants",
        "accountant_norm_covid_caption": "No government subsidies identified",
        "accountant_norm_section_other": "4. Other Normalization Items",
        "accountant_norm_related_party": "Related Party Transactions (Above/Below Market)",
        "accountant_norm_related_party_caption": "No related party transactions at non-arm's length terms",
        "accountant_norm_excess_rent": "Excess Rent / Below-Market Rent",
        "accountant_norm_excess_rent_caption": "Rent expense at market rate",
        "accountant_norm_professional_fees": "Professional Fees (Non-Recurring Advisory)",
        "accountant_norm_professional_fees_caption": "No one-time advisory fees identified",
        "accountant_norm_total_label": "Total Normalization Adjustments",
        "accountant_norm_adjustments_applied": "Adjustments applied",
        "accountant_norm_no_material": "No material adjustments required",
        "accountant_norm_status_reviewed": "Reviewed",
        "accountant_norm_status_standard": "Standard",
        "accountant_norm_normalized_label": "Normalized EBITDA",
        "accountant_norm_sustainable_earning": "Sustainable Earning Power",
        "accountant_norm_valuation_basis": "Valuation Basis",
        "accountant_norm_data_limit_title": "Data Limitation Notice",
        "accountant_norm_data_limit_body": (
            "<strong>Limited Visibility:</strong> This normalization schedule is prepared with "
            "{availability} financial data visibility. A comprehensive ASA BVS-III Quality of "
            "Earnings analysis requires access to:"
        ),
        "accountant_norm_data_limit_default_avail": "limited",
        "accountant_norm_data_limit_item1": "Detailed general ledger (G/L) breakdown by expense category",
        "accountant_norm_data_limit_item2": "Owner compensation documentation (employment contracts, benefit details)",
        "accountant_norm_data_limit_item3": "Multi-year historical financials (3-5 years recommended)",
        "accountant_norm_data_limit_item4": "Tax returns for cross-reference validation",
        "accountant_norm_data_limit_footer": (
            "The valuation applies <strong>conservative quality adjustments to the "
            "multiple</strong> (Step 2.5: Quality Calibration) to account for potential "
            "undisclosed owner benefits and discretionary expenses."
        ),
        "accountant_norm_categories_title": "ASA BVS-III Normalization Categories",
        "accountant_norm_standard_categories": "Standard Adjustment Categories",
        "accountant_norm_cat_owner": "<strong>Owner Compensation:</strong> Adjust to market replacement rate",
        "accountant_norm_cat_personal": "<strong>Personal Expenses:</strong> Vehicles, travel, entertainment",
        "accountant_norm_cat_family": "<strong>Family Members:</strong> Above-market family compensation",
        "accountant_norm_cat_nonrecurring": "<strong>Non-Recurring Items:</strong> One-time gains/losses",
        "accountant_norm_cat_related": "<strong>Related Party Transactions:</strong> Non-arm's length pricing",
        "accountant_norm_academic_foundation": "Academic Foundation",
        "accountant_norm_acad_trugman": "<strong>Trugman (2017):</strong> Chapter 8 - Normalization Framework",
        "accountant_norm_acad_hitchner": "<strong>Hitchner (2017):</strong> Chapter 11 - Quality of Earnings",
        "accountant_norm_acad_pratt": "<strong>Pratt & Niculita (2008):</strong> Chapter 14 - SME Adjustments",
        "accountant_norm_acad_asa": "<strong>ASA BVS-III:</strong> Quality of Earnings Standards",
        "accountant_norm_acad_aicpa": "<strong>AICPA BVS-VII:</strong> Comprehensive Valuation Requirements",
        "accountant_norm_enhanced_disclosure_title": "Enhanced Disclosure Requirement",
        "accountant_norm_enhanced_disclosure_body": (
            "<strong>Fiduciary Standard:</strong> For valuations supporting fairness opinions, "
            "litigation, or regulatory filings, ASA BVS-III requires a complete normalization "
            "schedule with detailed documentation of each adjustment category. This enhanced "
            "schedule represents the minimum framework; actual implementation requires access to "
            "detailed financial records and management interviews to quantify each category."
        ),
        # Phase 2: Vitality Dashboard
        "accountant_vitality_section_title": "Section 4.1 — Business Vitality & Financial Health",
        "accountant_vitality_intro": (
            "This section evaluates the Company's operational resilience through systematic "
            "analysis of liquidity, solvency, and efficiency metrics. Our assessment framework "
            "applies <strong>Primitive 4: Shared Reality</strong> standards to quantify "
            "structural health indicators that institutional investors prioritize when assessing "
            "SME acquisition targets."
        ),
        "accountant_vitality_market_context": (
            "<strong>Market Context:</strong> Empirical research indicates that institutional "
            "buyers systematically adjust valuation multiples based on vitality assessments. "
            "Companies demonstrating strong vitality scores (75%+) typically command 15-25% "
            "valuation premiums, while weak vitality metrics trigger 0.3x-0.5x multiple discounts "
            "due to heightened perceived transaction risk."
        ),
        "accountant_vitality_liquidity_title": "Liquidity & Solvency Assessment",
        "accountant_vitality_liquidity_intro": (
            "Operational resilience is a function of liquidity, solvency, and efficiency. This "
            "dashboard provides a high-level assessment of the Company's structural health "
            "compared to industry benchmarks, identifying potential vulnerabilities that could "
            "impact enterprise value."
        ),
        "accountant_vitality_caption": "Vitality Metrics Assessment",
        "accountant_vitality_col_indicator": "Health Indicator",
        "accountant_vitality_col_value": "Value",
        "accountant_vitality_col_assessment": "Assessment",
        "accountant_vitality_col_impact": "Valuation Impact",
        "accountant_vitality_score_summary_title": "Vitality Score Summary",
        "accountant_vitality_score_label": "Business Vitality Score",
        "accountant_vitality_excellent": "<strong>Excellent Vitality:</strong> Strong liquidity and solvency position supports premium valuation multiples",
        "accountant_vitality_moderate": "<strong>Moderate Vitality:</strong> Acceptable structural health with room for operational improvements",
        "accountant_vitality_weak": "<strong>Weak Vitality:</strong> Significant structural vulnerabilities may trigger valuation discounts",
        "accountant_vitality_unavailable_title": "Vitality Metrics Unavailable",
        "accountant_vitality_unavailable_body": "Financial health data is not available for vitality assessment. This represents a material limitation for comprehensive risk evaluation.",
        "accountant_vitality_growth_title": "Growth Trajectory Analysis",
        "accountant_vitality_growth_intro": (
            "Sustainable growth patterns are critical indicators of business vitality. This "
            "analysis evaluates historical growth trends and their implications for future "
            "performance predictability."
        ),
        "accountant_vitality_primitive_title": "Primitive 4: Shared Reality Framework",
        "accountant_vitality_primitive_body": (
            "<strong>IVS 105:</strong> Valuation must consider all factors that market "
            "participants would reasonably consider. Business vitality metrics provide the "
            "empirical foundation for assessing enterprise risk and determining appropriate "
            "valuation adjustments."
        ),
        # Phase 2: Data Quality Compliance
        "accountant_dq_section_title": "Section 4.2 — Data Quality & Professional Standards Compliance",
        "accountant_dq_intro": (
            "Data quality assessment establishes the foundation of valuation credibility by "
            "systematically evaluating the integrity, completeness, and reliability of financial "
            "information. This section applies <strong>ASA BVS-III</strong> standards to "
            "quantify data confidence levels and their impact on valuation certainty."
        ),
        "accountant_dq_pro_standard": (
            "<strong>Professional Standard:</strong> USPAP requires valuation professionals to "
            "assess data quality and adjust confidence levels accordingly. Low-quality data "
            "triggers valuation discounts of 0.2x-0.4x to reflect increased uncertainty and due "
            "diligence risk."
        ),
        "accountant_dq_assessment_title": "Data Quality Assessment",
        "accountant_dq_assessment_intro": (
            "The reliability of this valuation is anchored in the integrity of the underlying "
            "financial data. We assess the documentation quality to ensure the 'Economic Truth' "
            "Primitive is maintained and quantify the confidence level for institutional "
            "stakeholders."
        ),
        "accountant_dq_overall_label": "Overall Data Quality",
        "accountant_dq_overall_caption": "Integrity of inputs and documentation",
        "accountant_dq_confidence_label": "Confidence Score",
        "accountant_dq_confidence_caption": "Defensibility rating for valuation conclusion",
        "accountant_dq_dimensions_title": "Quality Dimensions",
        "accountant_dq_dim_completeness": "Documentation coverage and data availability",
        "accountant_dq_dim_accuracy": "Numerical precision and calculation verification",
        "accountant_dq_dim_consistency": "Internal coherence and cross-validation",
        "accountant_dq_dim_timeliness": "Currency of financial information",
        "accountant_dq_dim_default": "Quality assessment dimension",
        "accountant_dq_warnings_title": "Data Quality Warnings",
        "accountant_dq_recommendation_label": "Recommendation:",
        "accountant_dq_unavailable_title": "Data Quality Assessment Unavailable",
        "accountant_dq_unavailable_body": "Detailed data quality metrics are not available for this valuation. This represents a material limitation affecting confidence in the valuation conclusion.",
        "accountant_dq_guardrail_title": "Academic Guardrail",
        "accountant_dq_guardrail_body": (
            "<strong>Hitchner (2017):</strong> Financial analysis must precede valuation to "
            "identify distortions and ensure the sustainability of the earnings base. This "
            "assessment complies with the quantitative analysis requirements of <strong>ASA "
            "BVS-III</strong> and <strong>USPAP</strong> standards for data quality evaluation."
        ),
        # Phase 2: Strategic Roadmap
        "accountant_roadmap_section_title": "Section 5 — Valuation Conclusion & Market Context",
        "accountant_roadmap_intro": (
            "This section presents the culmination of the valuation analysis, integrating market "
            "transaction benchmarks with the final enterprise value conclusion. In accordance "
            "with <strong>USPAP Standard 10</strong> and <strong>IVS 105 (Valuation Approaches "
            "and Methods)</strong>, we provide comparative market multiples alongside the "
            "synthesized valuation range to enable informed strategic decision-making."
        ),
        "accountant_roadmap_consistency": (
            "<strong>Methodological Consistency:</strong> Transaction multiples are calibrated "
            "against comparable sales data from similar enterprises, systematically adjusted for "
            "size differentials, growth trajectories, and risk profiles. The final valuation "
            "conclusion incorporates all methodological adjustments while maintaining "
            "mathematical reconciliation and professional defensibility."
        ),
        "accountant_roadmap_benchmarks_title": "Market Transaction Benchmarks",
        "accountant_roadmap_industry_multiples": "Industry-Specific Transaction Multiples",
        "accountant_roadmap_ev_ebitda_label": "EV/EBITDA Multiple",
        "accountant_roadmap_median_label": "Median",
        "accountant_roadmap_multiple_range": "Multiple Range",
        "accountant_roadmap_p25_p75": "P25-P75",
        "accountant_roadmap_typical_margin": "Typical EBITDA Margin",
        "accountant_roadmap_industry_label": "Industry",
        "accountant_roadmap_synthesized_label": "Synthesized Intrinsic Value (Equity)",
        "accountant_roadmap_valuation_range_label": "Valuation Range",
        "accountant_roadmap_to_label": "to",
        "accountant_roadmap_listing_price_label": "Suggested Listing Price",
        "accountant_roadmap_premium_suffix": "Premium",
        "accountant_roadmap_premium_caption": "Strategic premium applied to multiple; provides negotiation buffer.",
        "accountant_roadmap_not_available": "Not available",
        # Phase 2: Strategic Assessment
        "accountant_strategic_section_title": "Section 1.1 — Strategic Assessment & Value Optimization",
        "accountant_strategic_intro": (
            "This section provides a systematic assessment of the Company's strategic "
            "positioning and identifies value optimization opportunities. Our analysis draws from "
            "empirical valuation research and comparable transaction data to quantify both "
            "current value drivers and actionable improvements that enhance enterprise value."
        ),
        "accountant_strategic_methodology": (
            "<strong>Methodological Foundation:</strong> This assessment adheres to USPAP "
            "Standard 9 and IVS 105, incorporating market-derived adjustments from comparable "
            "transaction analysis. All value drivers and risk factors are calculated from actual "
            "financial data, supported by academic research (Damodaran 2012, Koller 2020, Trugman "
            "2017)."
        ),
        "accountant_strategic_drivers_title": "Primary Value Drivers",
        "accountant_strategic_drivers_intro": (
            "The following factors currently support the Company's valuation and represent "
            "sustainable competitive advantages."
        ),
        "accountant_strategic_risks_title": "Critical Risk Considerations",
        "accountant_strategic_risks_intro": (
            "These factors currently constrain valuation multiples and represent areas requiring "
            "management attention to unlock full enterprise value."
        ),
        # Phase 2: User Normalization
        "accountant_un_section_title": "Section 2 — Economic Reality (User-Defined EBITDA Normalization)",
        "accountant_un_methodology_note": (
            "<strong>Methodology Note:</strong> The following EBITDA normalization adjustments "
            "were performed by the user to reconstruct sustainable earning power. These "
            "adjustments reflect user-specific knowledge of the business operations and financial "
            "structure, and replace automated normalization calculations."
        ),
        "accountant_un_year_normalization": "Normalization",
        "accountant_un_bridge_caption": "EBITDA Normalization Bridge",
        "accountant_un_col_item": "Item",
        "accountant_un_col_amount": "Amount (€)",
        "accountant_un_col_rationale": "Rationale",
        "accountant_un_reported_ebitda": "Reported EBITDA",
        "accountant_un_as_shown": "As shown in financial statements",
        "accountant_un_custom_label": "CUSTOM",
        "accountant_un_total_adjustments": "Total Adjustments",
        "accountant_un_of_reported": "% of reported",
        "accountant_un_normalized": "Normalized EBITDA",
        "accountant_un_true_performance": "True operating performance",
        "accountant_un_performed_label": "Normalization performed:",
        "accountant_un_confidence_label": "Confidence level:",
        "accountant_un_version_label": "Valuation version:",
        "accountant_un_disclosure_title": "User Normalization Disclosure",
        "accountant_un_disclosure_body": (
            "These user-defined adjustments replace the automated normalization calculations "
            "that would otherwise be performed in Step 2.5 (Quality Calibration). The valuation "
            "has been calculated using the normalized EBITDA values shown above. All adjustments "
            "have been documented with rationale and are included in the complete audit trail. "
            "This normalization methodology follows commonly applied professional practice for "
            "EBITDA reconstruction in SME valuations."
        ),
        # Phase 2: Growth Metrics
        "accountant_growth_title": "Growth Metrics Analysis",
        "accountant_growth_cagr3y": "3-Year CAGR",
        "accountant_growth_cagr_caption": "Compounded annual growth.",
        "accountant_growth_yoy": "YoY Revenue Growth",
        "accountant_growth_yoy_caption": "Latest fiscal year.",
        "accountant_growth_historical_title": "Historical Growth Trends",
        "accountant_growth_col_year": "Year",
        "accountant_growth_col_revenue": "Revenue",
        "accountant_growth_col_growth": "Growth",
        "accountant_growth_trajectory_positive": "<strong>Growth Trajectory:</strong> Positive CAGR indicates consistent growth over the analysis period, serving as a key value driver for the valuation.",
        "accountant_growth_trajectory_negative": "<strong>Growth Trajectory:</strong> Negative CAGR indicates declining revenue trends, which may impact valuation multiples and future growth assumptions.",
        "accountant_growth_trajectory_flat": "<strong>Growth Trajectory:</strong> Stable revenue profile with flat growth over the analysis period.",
        "accountant_growth_insufficient": "<strong>Insufficient Data:</strong> Unable to calculate growth metrics. At least 2 years of historical financial data are required.",
        # Phase 2: SME Expert Rationale
        "accountant_sme_title": "SME Expert Analysis: Business Type & Company Characteristics",
        "accountant_sme_business_type_classification": "Business Type Classification",
        "accountant_sme_business_type_label": "Business Type",
        "accountant_sme_business_type_id_label": "Business Type ID",
        "accountant_sme_industry_label": "Industry",
        "accountant_sme_insight_classification": "SME Expert Insight - World-Class Business Type Classification:",
        "accountant_sme_insight_with_type": (
            "Business type <strong>{type}</strong> is one of <strong>188 distinct business "
            "types</strong> in our comprehensive database. This classification enables "
            "<strong>world-class SME valuation</strong> that goes far beyond generic industry "
            "averages."
        ),
        "accountant_sme_insight_no_type": (
            "This valuation uses <strong>business-type-specific logic</strong> from our database "
            "of <strong>188 distinct business types</strong>. This enables world-class SME "
            "valuation precision."
        ),
        "accountant_sme_how_label": "How Business Type Influences Valuation:",
        "accountant_sme_multiple_selection": "Multiple Selection:",
        "accountant_sme_multiple_db_default": "Business-type-specific SME multiples from regional market data (VFB Belgium 2024, Vlerick 2023)",
        "accountant_sme_multiple_other_default": "Business-type-specific EBITDA multiples are selected from regional SME market sources",
        "accountant_sme_multiple_suffix": "rather than generic industry databases. This ensures multiples reflect the unique risk profile of this business type.",
        "accountant_sme_owner_dep_label": "Owner Dependency Adjustments:",
        "accountant_sme_owner_dep_body": (
            "Each business type has specific owner dependency characteristics that directly "
            "influence owner concentration adjustments. Business types with high owner dependency "
            "(e.g., consulting, professional services) receive higher discounts than scalable "
            "business types (e.g., SaaS, e-commerce)."
        ),
        "accountant_sme_margin_label": "Margin-Based Adjustments:",
        "accountant_sme_margin_body": (
            "Business-type-specific typical EBITDA margins serve as benchmarks. If actual margins "
            "significantly deviate from business-type-specific benchmarks, margin adjustments are "
            "applied to reflect operational risk."
        ),
        "accountant_sme_methodology_sel_label": "Methodology Selection:",
        "accountant_sme_methodology_sel_body": (
            "Business-type-specific methodology preferences guide whether DCF or multiples is "
            "more appropriate. Business types with high owner dependency or limited forward "
            "visibility prefer multiples over DCF."
        ),
        "accountant_sme_academic_basis": "Academic Basis:",
        "accountant_sme_academic_body": (
            "Trugman (2017), Coulon (2021), and VFB Belgium (2024) document that SME valuations "
            "require business-type-specific adjustments, not generic industry multiples. Our "
            "database of 188 business types enables <strong>world-class SME valuation</strong> "
            "that reflects the unique characteristics of each business type, matching the "
            "precision of International Valuation Standards (IVS 2017) and academic SME "
            "valuation practices."
        ),
        "accountant_sme_growth_stage_title": "Growth Stage Analysis",
        "accountant_sme_growth_stage_label": "Company Growth Stage",
        "accountant_sme_risk_adj_label": "Risk Adjustment",
        "accountant_sme_startup_adj": "-5% to -10% multiple reduction",
        "accountant_sme_stable_stage": "Stable Stage",
        "accountant_sme_stable_no_adj": "No growth stage adjustment",
        "accountant_sme_mature_stage": "Mature Stage",
        "accountant_sme_mature_lower_risk": "Lower risk profile",
        "accountant_sme_insight_label": "SME Expert Insight:",
        "accountant_sme_startup_body": (
            "<strong>Startup Stage ({stage})</strong>: Companies less than 3 years old or with "
            "high revenue volatility (>50%) face elevated risk. Per academic research (Trugman "
            "2017, Coulon 2021), startup SMEs require -5% to -10% multiple reduction to account "
            "for: (1) Unproven business model, (2) Limited operating history, (3) Higher failure "
            "risk, (4) Buyer skepticism. The exact adjustment (-5% to -10%) scales with company "
            "age: newer companies receive higher discounts."
        ),
        "accountant_sme_growth_body": (
            "<strong>Growth Stage ({stage})</strong>: Companies 3-10 years old with stable "
            "revenue growth patterns. This stage indicates proven business model and operational "
            "stability. No growth stage adjustment is applied, as the company has demonstrated "
            "viability and market acceptance."
        ),
        "accountant_sme_mature_body": (
            "<strong>Mature Stage ({stage})</strong>: Companies over 10 years old with "
            "established operations. Mature SMEs have lower risk profiles due to proven track "
            "record, stable operations, and market position. No growth stage discount is "
            "applied, reflecting the lower risk premium buyers require."
        ),
        "accountant_sme_owner_dep_title": "Owner Dependency Analysis",
        "accountant_sme_owner_dep_impact_label": "Owner Dependency Impact",
        "accountant_sme_high_risk": "High Risk",
        "accountant_sme_medium_risk": "Medium Risk",
        "accountant_sme_low_risk": "Low Risk",
        "accountant_sme_high_dep_caption": "Significant key person dependency - business value heavily tied to owner",
        "accountant_sme_med_dep_caption": "Moderate key person dependency - some operational independence",
        "accountant_sme_low_dep_caption": "Low key person dependency - strong operational independence",
        "accountant_sme_owner_dep_intro": "Owner dependency impact of",
        "accountant_sme_owner_dep_intro_suffix": "is derived from business type characteristics in our database.",
        "accountant_sme_owner_dep_high": (
            "<strong>High owner dependency (≥70%)</strong> indicates the business is heavily "
            "dependent on the owner's personal relationships, expertise, or presence. This "
            "creates significant transferability risk, as buyers cannot easily replace the "
            "owner's value contribution. Per Astrachan & Jaskiewicz (2008) and Hitchner (2017), "
            "high owner dependency typically results in 15-25% valuation discounts for SMEs."
        ),
        "accountant_sme_owner_dep_medium": (
            "<strong>Medium owner dependency (40-70%)</strong> indicates moderate reliance on "
            "the owner, with some operational systems and management depth in place. This "
            "creates moderate transferability risk. Per academic research, medium owner "
            "dependency typically results in 7-15% valuation discounts."
        ),
        "accountant_sme_owner_dep_low": (
            "<strong>Low owner dependency (<40%)</strong> indicates strong operational "
            "independence with established systems, management depth, and institutional "
            "knowledge. This creates minimal transferability risk. Per academic research, low "
            "owner dependency typically results in 0-7% valuation discounts."
        ),
        "accountant_sme_owner_dep_footer": "This business-type-specific owner dependency impact directly influences the owner concentration adjustment in Step 4.",
        "accountant_sme_adj_breakdown_title": "SME-Specific Adjustments Applied",
        "accountant_sme_adj_breakdown_intro": (
            "These adjustments are <strong>SME-specific</strong> and differ from large company "
            "valuation logic. Each adjustment is based on academic research (Trugman 2017, "
            "Coulon 2021, VFB Belgium 2024, Vlerick 2023) and reflects the unique risk profile "
            "of SMEs. The adjustments account for:"
        ),
        "accountant_sme_adj_size": "<strong>Size-related risk</strong>: SMEs face higher operational fragility than large companies,",
        "accountant_sme_adj_type": "<strong>Business type characteristics</strong>: Owner dependency, typical margins, and scalability vary by business type,",
        "accountant_sme_adj_growth": "<strong>Growth stage</strong>: Startup companies face higher risk than mature companies,",
        "accountant_sme_adj_market": "<strong>Market-specific factors</strong>: Belgian SME market multiples differ from generic databases.",
        "accountant_sme_adj_academic": (
            "<strong>Academic Basis:</strong> Koller, Goedhart & Wessels (2020) and Trugman "
            "(2017) document that SME valuations require systematic adjustments to avoid "
            "overvaluation from large-company database multiples."
        ),
        # Phase 2: Business Type Analysis
        "accountant_bta_strategic_profile": "Strategic Valuation Profile",
        "accountant_bta_methodology_fit": "Market Multiples Preferred",
        "accountant_bta_methodology_alignment": "Methodology Alignment",
        "accountant_bta_multiples_fit": "Multiples Fit",
        "accountant_bta_high_volume_caption": "High volume of transaction data available for {type}. Market comparisons provide stronger evidence than theoretical cash flows.",
        "accountant_bta_key_person_risk": "Key Person Risk",
        "accountant_bta_impact_label": "Impact",
        "accountant_bta_critical_risk": "Critical risk factor. Value heavily tied to owner relationships. Significant discount justified.",
        "accountant_bta_moderate_risk": "Moderate risk factor. Transition plan required to preserve value.",
        "accountant_bta_low_risk_caption": "Low risk factor. Operations sustainable without current owner.",
        "accountant_bta_standard_risk": "Standard risk factor. Specific impact data unavailable for this business type.",
        "accountant_bta_sector_margin": "Sector Margin",
        "accountant_bta_target_label": "Target",
        "accountant_bta_benchmark_caption": "Benchmark median EBITDA margin for {type}. Deviations trigger specific risk adjustments in the model.",
        "accountant_bta_academic_basis_label": "Academic Basis",
        "accountant_bta_academic_basis_ref": "Ref: Trugman (2017), Coulon (2021) • SME Valuation Standards",
        "accountant_cond_data_not_available_title": "Data Not Available",
        "accountant_cond_data_not_available_default": "The requested data is not available for this company. This may be due to insufficient historical information or data collection limitations.",
        "accountant_cond_limited_data_title": "Limited Data Warning",
        "accountant_cond_limited_data_default": "This analysis is based on limited historical data. Results should be interpreted with caution.",
        "accountant_cond_limited_data_impact": "Impact on Valuation:",
        "accountant_cond_neg_revenue_title": "Valuation Approach: Revenue Multiples",
        "accountant_cond_neg_revenue_body": "The company is currently operating at negative EBITDA margins while investing in growth. Revenue multiples are more appropriate than EBITDA multiples for companies in growth/investment phases. This approach is consistent with valuation of high-growth companies (Damodaran, 2017).",
        "accountant_cond_neg_high_risk_title": "High Risk Valuation Scenario",
        "accountant_cond_neg_high_risk_body": "Significant operating losses require substantial risk adjustments. The valuation range is widened to ±40% to reflect uncertainty. Path to profitability assumptions are critical for valuation reliability.",
        "accountant_cond_neg_not_determinable_title": "Limited Valuation Applicability",
        "accountant_cond_neg_not_determinable_body": "Sustained losses and declining revenue indicate going concern uncertainty. Traditional valuation methods assume profitable operations. Asset-based or liquidation value may be more appropriate (FASB ASC 205-40). Users should consider turnaround analysis and consult with turnaround specialists.",
        "accountant_cond_class_subject_to": "This report is subject to significant limitations due to:",
        "accountant_cond_class_caution": "Users should exercise caution and consult with professional advisors before relying on these conclusions.",
        "accountant_cond_class_special_purpose": "This valuation is for special purposes only and may not be appropriate for transaction pricing or financial reporting.",
    }
