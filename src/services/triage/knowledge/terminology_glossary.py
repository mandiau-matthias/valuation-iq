"""
Terminology Glossary

Local terminology glossary with multi-language support for financial,
valuation, legal, and tax terms. Provides instant lookups without API calls.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TermCategory(str, Enum):
    FINANCIAL_METRICS = "financial_metrics"
    VALUATION = "valuation"
    LEGAL = "legal"
    TAX = "tax"
    BUSINESS = "business"
    ACCOUNTING = "accounting"


@dataclass
class GlossaryEntry:
    term: str
    category: TermCategory
    definition: str
    examples: List[str] = field(default_factory=list)
    related_terms: List[str] = field(default_factory=list)
    why_it_matters: str = ""
    language: str = "en"


def _build_glossary() -> Dict[str, Dict[str, GlossaryEntry]]:
    """Build the multi-language glossary database."""
    db: Dict[str, Dict[str, GlossaryEntry]] = {"en": {}, "nl": {}, "fr": {}}

    en = db["en"]
    en["ebitda"] = GlossaryEntry(
        term="EBITDA",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Earnings Before Interest, Taxes, Depreciation, and Amortization. A measure of operating profitability that strips out financing and accounting decisions.",
        examples=[
            "If revenue is €1,000,000 and operating costs are €700,000, EBITDA is €300,000.",
            "A company with €500,000 EBITDA and a 10x multiple is worth €5,000,000.",
        ],
        related_terms=["Revenue", "Profit", "Operating Income", "Cash Flow"],
        why_it_matters="EBITDA is the most common metric used in business valuation. It allows comparison across companies by removing differences in capital structure and tax strategies.",
    )
    en["revenue"] = GlossaryEntry(
        term="Revenue",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Total income generated from business operations before any expenses are deducted. Also known as sales or turnover.",
        examples=[
            "A restaurant with 50,000 customers spending €20 each has €1,000,000 in revenue.",
            "SaaS company with 1,000 subscribers at €100/month = €1,200,000 annual revenue.",
        ],
        related_terms=["EBITDA", "Profit", "Turnover", "Sales"],
        why_it_matters="Revenue is the starting point for most valuation methods and indicates the scale of operations.",
    )
    en["profit"] = GlossaryEntry(
        term="Profit",
        category=TermCategory.FINANCIAL_METRICS,
        definition="The financial gain remaining after all expenses, taxes, and costs have been deducted from revenue.",
        examples=[
            "Revenue €500,000 minus expenses €400,000 equals €100,000 profit.",
            "Net profit margin of 20% means €200,000 profit on €1,000,000 revenue.",
        ],
        related_terms=["Revenue", "EBITDA", "Net Income", "Margin"],
        why_it_matters="Profitability directly impacts business valuation and indicates sustainability.",
    )
    en["valuation"] = GlossaryEntry(
        term="Valuation",
        category=TermCategory.VALUATION,
        definition="The process of determining the economic worth of a business or asset using financial analysis, market comparisons, and projections.",
        examples=[
            "A business valued at 5x EBITDA of €200,000 = €1,000,000.",
            "DCF valuation projects 5 years of future cash flows.",
        ],
        related_terms=["Multiple", "DCF", "Enterprise Value", "Equity Value"],
        why_it_matters="Accurate valuation is essential for M&A transactions, investment decisions, and strategic planning.",
    )
    en["multiple"] = GlossaryEntry(
        term="Multiple",
        category=TermCategory.VALUATION,
        definition="A ratio used to value a business by multiplying a financial metric (like EBITDA or revenue) by a factor derived from comparable transactions.",
        examples=[
            "An EBITDA multiple of 8x means the business is valued at 8 times its EBITDA.",
            "Revenue multiples for SaaS companies range from 3x to 15x.",
        ],
        related_terms=["EBITDA", "Revenue", "Valuation", "Comparables"],
        why_it_matters="Multiples are the most common valuation method for SMEs and provide market-based pricing.",
    )
    en["cash flow"] = GlossaryEntry(
        term="Cash Flow",
        category=TermCategory.FINANCIAL_METRICS,
        definition="The net amount of cash moving in and out of a business. Positive cash flow means more money coming in than going out.",
        examples=[
            "Operating cash flow of €250,000 after paying all operating expenses.",
            "Free cash flow = Operating cash flow minus capital expenditures.",
        ],
        related_terms=["EBITDA", "Revenue", "Working Capital", "Free Cash Flow"],
        why_it_matters="Cash flow indicates the actual financial health and ability to sustain operations, unlike accounting profits.",
    )
    en["assets"] = GlossaryEntry(
        term="Assets",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Resources owned by a business that have economic value, including property, equipment, inventory, cash, and receivables.",
        examples=[
            "Total assets of €2,000,000 including €500,000 in equipment.",
            "Current assets include €100,000 cash and €200,000 in receivables.",
        ],
        related_terms=["Liabilities", "Equity", "Balance Sheet", "Net Worth"],
        why_it_matters="Assets contribute to business valuation, especially for asset-heavy industries like manufacturing and real estate.",
    )
    en["asset"] = en["assets"]
    en["liabilities"] = GlossaryEntry(
        term="Liabilities",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Financial obligations or debts that a business owes to external parties, including loans, accounts payable, and other obligations.",
        examples=[
            "Long-term debt of €500,000 from bank loans.",
            "Current liabilities include €50,000 in accounts payable.",
        ],
        related_terms=["Assets", "Equity", "Debt", "Balance Sheet"],
        why_it_matters="Liabilities reduce equity value. Enterprise Value minus net debt equals equity value.",
    )
    en["liability"] = en["liabilities"]
    en["dcf"] = GlossaryEntry(
        term="DCF",
        category=TermCategory.VALUATION,
        definition="Discounted Cash Flow - a valuation method that projects future cash flows and discounts them back to present value using a discount rate.",
        examples=[
            "5-year DCF with 10% discount rate values the business at €1,500,000.",
            "Terminal value represents 60-80% of total DCF valuation.",
        ],
        related_terms=["Valuation", "Cash Flow", "Discount Rate", "Terminal Value"],
        why_it_matters="DCF provides an intrinsic valuation based on a company's fundamentals rather than market comparisons.",
    )
    en["enterprise value"] = GlossaryEntry(
        term="Enterprise Value",
        category=TermCategory.VALUATION,
        definition="The total value of a business including equity and debt, minus cash. Represents the theoretical takeover price.",
        examples=[
            "Enterprise Value = Equity Value + Total Debt - Cash.",
            "EV of €5,000,000 with €1,000,000 debt and €200,000 cash = €4,200,000 equity.",
        ],
        related_terms=["Equity Value", "Valuation", "Debt", "Multiple"],
        why_it_matters="Enterprise Value is the standard measure for comparing businesses regardless of their capital structure.",
    )
    en["equity value"] = GlossaryEntry(
        term="Equity Value",
        category=TermCategory.VALUATION,
        definition="The value of a business that belongs to the shareholders after subtracting all debts. Also called market capitalization for public companies.",
        examples=[
            "Enterprise Value €5,000,000 - Net Debt €1,000,000 = Equity Value €4,000,000.",
            "The asking price for the business reflects its equity value.",
        ],
        related_terms=["Enterprise Value", "Valuation", "Shareholders", "Net Worth"],
        why_it_matters="Equity Value is what a buyer actually pays for ownership of the business.",
    )
    en["margin"] = GlossaryEntry(
        term="Margin",
        category=TermCategory.FINANCIAL_METRICS,
        definition="The percentage of revenue remaining after deducting costs. Different margins (gross, operating, net) measure profitability at different levels.",
        examples=[
            "EBITDA margin of 20% means €200,000 EBITDA on €1,000,000 revenue.",
            "Gross margin of 60% after deducting cost of goods sold.",
        ],
        related_terms=["EBITDA", "Revenue", "Profit", "Operating Income"],
        why_it_matters="Margins indicate efficiency and profitability, directly impacting valuation multiples.",
    )
    en["net income"] = GlossaryEntry(
        term="Net Income",
        category=TermCategory.FINANCIAL_METRICS,
        definition="The total profit after all expenses, including taxes and interest, have been deducted from revenue. The bottom line.",
        examples=[
            "Revenue €1,000,000 minus all expenses = Net income €120,000.",
            "Net income margin of 12% is considered healthy for most industries.",
        ],
        related_terms=["Revenue", "EBITDA", "Profit", "Taxes"],
        why_it_matters="Net income reflects the actual profitability available to shareholders.",
    )
    en["working capital"] = GlossaryEntry(
        term="Working Capital",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Current assets minus current liabilities. Measures short-term financial health and operational efficiency.",
        examples=[
            "Working capital of €200,000 (€500,000 current assets - €300,000 current liabilities).",
            "Negative working capital may indicate cash flow problems.",
        ],
        related_terms=["Assets", "Liabilities", "Cash Flow", "Liquidity"],
        why_it_matters="Working capital requirements affect the cash needed to run the business and impact its valuation.",
    )
    en["turnover"] = en["revenue"]
    en["sales"] = en["revenue"]
    en["debt"] = en["liabilities"]
    en["earnings"] = en["profit"]
    en["goodwill"] = GlossaryEntry(
        term="Goodwill",
        category=TermCategory.ACCOUNTING,
        definition="An intangible asset representing the premium paid over the fair value of a business's identifiable assets during an acquisition.",
        examples=["Acquisition price €2M minus net assets €1.5M = Goodwill €500,000."],
        related_terms=["Assets", "Acquisition", "Enterprise Value"],
        why_it_matters="Goodwill reflects the value of brand, customer relationships, and reputation in a valuation context.",
    )
    en["depreciation"] = GlossaryEntry(
        term="Depreciation",
        category=TermCategory.ACCOUNTING,
        definition="The systematic allocation of the cost of a tangible asset over its useful life.",
        examples=["A €100,000 machine depreciated over 10 years = €10,000/year."],
        related_terms=["EBITDA", "Amortization", "Assets", "Capital Expenditure"],
        why_it_matters="Depreciation is added back to EBITDA, making it a non-cash expense that affects valuation multiples.",
    )
    en["amortization"] = GlossaryEntry(
        term="Amortization",
        category=TermCategory.ACCOUNTING,
        definition="The gradual write-off of an intangible asset's cost over its estimated useful life.",
        examples=["Patent costs of €50,000 amortized over 5 years = €10,000/year."],
        related_terms=["EBITDA", "Depreciation", "Intangible Assets"],
        why_it_matters="Like depreciation, amortization is a non-cash charge added back for EBITDA calculation.",
    )
    en["interest"] = GlossaryEntry(
        term="Interest",
        category=TermCategory.FINANCIAL_METRICS,
        definition="The cost of borrowing money, paid as a percentage of the outstanding loan amount.",
        examples=["€500,000 loan at 5% interest = €25,000 annual interest expense."],
        related_terms=["Debt", "EBITDA", "Liabilities", "Cash Flow"],
        why_it_matters="Interest expense is excluded from EBITDA to compare businesses regardless of their financing structure.",
    )
    en["capital expenditure"] = GlossaryEntry(
        term="Capital Expenditure",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Funds used by a business to acquire, upgrade, or maintain physical assets such as property, equipment, or technology.",
        examples=["Purchasing new machinery for €200,000 is a capital expenditure."],
        related_terms=["Cash Flow", "Depreciation", "Assets", "Free Cash Flow"],
        why_it_matters="CapEx impacts free cash flow and thus DCF valuation models.",
    )
    en["free cash flow"] = GlossaryEntry(
        term="Free Cash Flow",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Operating cash flow minus capital expenditures. Represents cash available to debt and equity holders.",
        examples=["Operating cash flow €300,000 minus CapEx €100,000 = FCF €200,000."],
        related_terms=["Cash Flow", "Capital Expenditure", "EBITDA", "DCF"],
        why_it_matters="Free cash flow is the foundation of DCF valuation methodology.",
    )
    en["balance sheet"] = GlossaryEntry(
        term="Balance Sheet",
        category=TermCategory.ACCOUNTING,
        definition="A financial statement reporting a company's assets, liabilities, and shareholders' equity at a specific point in time.",
        examples=["Total assets €2M = Total liabilities €1.2M + Equity €800,000."],
        related_terms=["Assets", "Liabilities", "Equity", "Financial Statements"],
        why_it_matters="The balance sheet provides critical data for enterprise value to equity value conversion in valuations.",
    )
    en["operating income"] = GlossaryEntry(
        term="Operating Income",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Profit from core business operations, excluding interest and taxes. Also known as EBIT (Earnings Before Interest and Taxes).",
        examples=["Revenue €1M minus COGS €600K minus OpEx €200K = Operating Income €200K."],
        related_terms=["EBITDA", "Revenue", "Profit", "EBIT"],
        why_it_matters="Operating income shows the profitability of core operations, a key input for valuation.",
    )
    en["discount rate"] = GlossaryEntry(
        term="Discount Rate",
        category=TermCategory.VALUATION,
        definition="The rate used to discount future cash flows back to their present value, reflecting the time value of money and risk.",
        examples=["A 10% discount rate means €110 in one year is worth €100 today."],
        related_terms=["DCF", "WACC", "Terminal Value", "Risk"],
        why_it_matters="The discount rate is a critical input in DCF valuations that significantly impacts the final value.",
    )
    en["comparables"] = GlossaryEntry(
        term="Comparables",
        category=TermCategory.VALUATION,
        definition="Similar companies or transactions used as benchmarks to derive valuation multiples.",
        examples=["10 comparable SaaS companies with median revenue multiple of 5x."],
        related_terms=["Multiple", "Valuation", "Benchmarking"],
        why_it_matters="Comparable analysis provides market-based evidence for fair valuation.",
    )

    nl = db["nl"]
    nl["ebitda"] = GlossaryEntry(
        term="EBITDA",
        category=TermCategory.FINANCIAL_METRICS,
        definition="EBITDA staat voor winst vóór rente, belastingen, afschrijvingen en amortisatie. Het meet de operationele winstgevendheid.",
        examples=["Omzet €1.000.000 minus bedrijfskosten €700.000 = EBITDA €300.000."],
        related_terms=["Omzet", "Winst", "Kasstroom"],
        why_it_matters="EBITDA is de meest gebruikte maatstaf bij bedrijfswaarderingen.",
        language="nl",
    )
    nl["omzet"] = GlossaryEntry(
        term="Omzet",
        category=TermCategory.FINANCIAL_METRICS,
        definition="De totale inkomsten uit bedrijfsactiviteiten vóór aftrek van kosten.",
        examples=["Jaarlijkse omzet van €2.000.000 uit productverkoop."],
        related_terms=["EBITDA", "Winst", "Verkoop"],
        why_it_matters="Omzet is het startpunt voor de meeste waarderingsmethoden.",
        language="nl",
    )
    nl["winst"] = GlossaryEntry(
        term="Winst",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Het financiële resultaat na aftrek van alle kosten, belastingen en lasten van de omzet.",
        examples=["Netto winst van €150.000 op een omzet van €1.000.000."],
        related_terms=["Omzet", "EBITDA", "Marge"],
        why_it_matters="Winstgevendheid heeft direct invloed op de bedrijfswaardering.",
        language="nl",
    )
    nl["waardering"] = GlossaryEntry(
        term="Waardering",
        category=TermCategory.VALUATION,
        definition="Het proces van het bepalen van de economische waarde van een bedrijf.",
        examples=["Een bedrijf gewaardeerd op 5x EBITDA van €200.000 = €1.000.000."],
        related_terms=["Multiple", "DCF", "Ondernemingswaarde"],
        why_it_matters="Nauwkeurige waardering is essentieel bij fusies, overnames en investeringen.",
        language="nl",
    )
    nl["revenue"] = nl["omzet"]
    nl["profit"] = nl["winst"]
    nl["valuation"] = nl["waardering"]

    fr = db["fr"]
    fr["ebitda"] = GlossaryEntry(
        term="EBITDA",
        category=TermCategory.FINANCIAL_METRICS,
        definition="EBITDA signifie bénéfice avant intérêts, impôts, dépréciation et amortissement. Il mesure la rentabilité opérationnelle.",
        examples=["Chiffre d'affaires €1.000.000 moins charges €700.000 = EBITDA €300.000."],
        related_terms=["Chiffre d'affaires", "Bénéfice", "Flux de trésorerie"],
        why_it_matters="L'EBITDA est la mesure la plus utilisée dans l'évaluation des entreprises.",
        language="fr",
    )
    fr["chiffre d'affaires"] = GlossaryEntry(
        term="Chiffre d'affaires",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Le revenu total généré par les activités commerciales avant toute déduction de charges.",
        examples=["Chiffre d'affaires annuel de €2.000.000."],
        related_terms=["EBITDA", "Bénéfice", "Ventes"],
        why_it_matters="Le chiffre d'affaires est le point de départ de la plupart des méthodes d'évaluation.",
        language="fr",
    )
    fr["revenue"] = fr["chiffre d'affaires"]
    fr["profit"] = GlossaryEntry(
        term="Bénéfice",
        category=TermCategory.FINANCIAL_METRICS,
        definition="Le gain financier restant après déduction de toutes les charges, impôts et coûts du chiffre d'affaires.",
        examples=["Bénéfice net de €150.000 sur un CA de €1.000.000."],
        related_terms=["Chiffre d'affaires", "EBITDA", "Marge"],
        why_it_matters="La rentabilité impacte directement la valorisation de l'entreprise.",
        language="fr",
    )
    fr["valuation"] = GlossaryEntry(
        term="Évaluation",
        category=TermCategory.VALUATION,
        definition="Le processus de détermination de la valeur économique d'une entreprise.",
        examples=["Entreprise évaluée à 5x EBITDA."],
        related_terms=["Multiple", "DCF", "Valeur d'entreprise"],
        why_it_matters="Une évaluation précise est essentielle pour les fusions-acquisitions.",
        language="fr",
    )

    return db


class TerminologyGlossary:
    def __init__(self) -> None:
        self._db = _build_glossary()

    def lookup(self, term: str, language: str = "en") -> Optional[GlossaryEntry]:
        if not term:
            return None
        cleaned = term.strip().lower()
        cleaned = re.sub(r"[!@#$%^&*()+=\[\]{}<>]", "", cleaned)

        lang_db = self._db.get(language, {})

        entry = lang_db.get(cleaned)
        if entry:
            return entry

        if cleaned.endswith("s") and len(cleaned) > 2:
            entry = lang_db.get(cleaned[:-1])
            if entry:
                return entry

        return None

    def search(self, query: str, language: str = "en", limit: int = 10) -> List[GlossaryEntry]:
        results: List[GlossaryEntry] = []
        query_lower = query.strip().lower()
        lang_db = self._db.get(language, {})

        seen_terms = set()
        for key, entry in lang_db.items():
            if entry.term in seen_terms:
                continue
            if (
                query_lower in key
                or query_lower in entry.definition.lower()
                or query_lower in entry.term.lower()
            ):
                results.append(entry)
                seen_terms.add(entry.term)
                if len(results) >= limit:
                    break

        return results

    def get_categories(self) -> List[str]:
        return [c.value for c in TermCategory]

    def get_terms_by_category(
        self, category: TermCategory, language: str = "en"
    ) -> List[GlossaryEntry]:
        lang_db = self._db.get(language, {})
        seen_terms = set()
        results = []
        for entry in lang_db.values():
            if entry.category == category and entry.term not in seen_terms:
                results.append(entry)
                seen_terms.add(entry.term)
        return results

    def get_term_count(self) -> int:
        count = 0
        for lang_db in self._db.values():
            seen = set()
            for entry in lang_db.values():
                if entry.term not in seen:
                    count += 1
                    seen.add(entry.term)
        return count
