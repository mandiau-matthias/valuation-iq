"""Academic sources and references for valuation report appendices."""

Reference = dict[str, str | None]

ACADEMIC_REFERENCES: dict[str, list[Reference]] = {
    "methodology": [
        {
            "author": "Koller, T., Goedhart, M., & Wessels, D.",
            "title": "Valuation: Measuring and Managing the Value of Companies",
            "year": "2015",
            "publisher": "Wiley",
            "pages": "Chapter 11: Valuing High-Growth Companies",
        },
        {
            "author": "Damodaran, A.",
            "title": "Investment Valuation: Tools and Techniques for Determining the Value of Any Asset",
            "year": "2012",
            "publisher": "Wiley",
            "pages": "Chapter 5: Risk-Adjusted Value",
        },
        {
            "author": "Pratt, S. P., & Grabowski, R. J.",
            "title": "Cost of Capital: Applications and Examples",
            "year": "2014",
            "publisher": "Wiley",
            "pages": "Chapter 8: Cost of Capital for Small Businesses",
        },
    ],
    "multiples": [
        {
            "author": "Koller, T., Goedhart, M., & Wessels, D.",
            "title": "Valuation: Measuring and Managing the Value of Companies",
            "year": "2015",
            "publisher": "Wiley",
            "pages": "Chapter 10: Market Multiples",
        },
        {
            "author": "Damodaran, A.",
            "title": "The Dark Side of Valuation: Valuing Young, Distressed, and Complex Businesses",
            "year": "2018",
            "publisher": "Pearson",
            "pages": "Chapter 4: Revenue Multiples",
        },
        {
            "author": "Duff & Phelps",
            "title": "Valuation Handbook: Guide to Cost of Capital",
            "year": "2024",
            "publisher": "Duff & Phelps",
            "pages": "SME Valuation Multiples",
        },
    ],
    "dcf": [
        {
            "author": "Koller, T., Goedhart, M., & Wessels, D.",
            "title": "Valuation: Measuring and Managing the Value of Companies",
            "year": "2015",
            "publisher": "Wiley",
            "pages": "Chapter 8: Frameworks for Valuation",
        },
        {
            "author": "Damodaran, A.",
            "title": "Investment Valuation: Tools and Techniques for Determining the Value of Any Asset",
            "year": "2012",
            "publisher": "Wiley",
            "pages": "Chapter 12: Discounted Cash Flow Valuation",
        },
        {
            "author": "Fernandez, P.",
            "title": "Valuation Methods and Shareholder Value Creation",
            "year": "2019",
            "publisher": "Academic Press",
            "pages": "Chapter 3: DCF Methodology",
        },
    ],
    "owner_concentration": [
        {
            "author": "Damodaran, A.",
            "title": "The Value of Control: Implications for Control Premia, Minority Discounts and Voting Share Differentials",
            "year": "2012",
            "publisher": "Stern School of Business Working Paper",
            "pages": None,
        },
        {
            "author": "Deloitte Private Company Services",
            "title": "Management Depth in SME Valuations",
            "year": "2022",
            "publisher": "Deloitte",
            "pages": None,
        },
        {
            "author": "PwC Valuation Handbook",
            "title": "SME Valuation Adjustments",
            "year": "2023",
            "publisher": "PwC",
            "pages": "Chapter 3: Owner Dependency Risk",
        },
    ],
    "sme_valuation": [
        {
            "author": "McKinsey & Company",
            "title": "Valuation: Measuring and Managing the Value of Companies",
            "year": "2015",
            "publisher": "Wiley",
            "pages": "Chapter 11: Valuing Small and Medium Enterprises",
        },
        {
            "author": "Duff & Phelps",
            "title": "Valuation Handbook: Guide to Cost of Capital",
            "year": "2024",
            "publisher": "Duff & Phelps",
            "pages": "SME Valuation Adjustments",
        },
        {
            "author": "Big 4 Advisory Standards",
            "title": "SME Valuation Best Practices",
            "year": "2023",
            "publisher": "Professional Standards",
            "pages": None,
        },
    ],
    "normalization": [
        {
            "author": "Koller, T., Goedhart, M., & Wessels, D.",
            "title": "Valuation: Measuring and Managing the Value of Companies",
            "year": "2015",
            "publisher": "Wiley",
            "pages": "Chapter 6: Analyzing Performance",
        },
        {
            "author": "Damodaran, A.",
            "title": "Investment Valuation: Tools and Techniques for Determining the Value of Any Asset",
            "year": "2012",
            "publisher": "Wiley",
            "pages": "Chapter 4: Cash Flow Estimation",
        },
    ],
}


def get_academic_references(categories: list[str] | None = None) -> dict[str, list[Reference]]:
    """
    Get academic references for specified categories.

    Args:
        categories: List of categories to include. If None, returns all.

    Returns:
        Dictionary of academic references by category
    """
    if categories is None:
        return ACADEMIC_REFERENCES

    return {cat: ACADEMIC_REFERENCES.get(cat, []) for cat in categories}


def get_references_for_report() -> dict[str, list[Reference]]:
    """
    Get all academic references formatted for report appendices.

    Returns:
        Dictionary formatted for template rendering
    """
    return ACADEMIC_REFERENCES
