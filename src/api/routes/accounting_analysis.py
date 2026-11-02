"""
Accounting analysis routes used by Titan for imported ledger snapshots.

These endpoints stay stateless: Titan sends normalized imported years and trial
balance rows, and ValuationIQ returns reusable enrichment outputs for bulk and
manual follow-up flows.
"""

from statistics import mean
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.middleware.auth import ServiceAccount, require_service_auth
from src.utils.logging import get_logger

router = APIRouter(prefix="/accounting-analysis", tags=["accounting-analysis"])
logger = get_logger(__name__)


class TrialBalanceEntryInput(BaseModel):
    account_code: str
    description: str = ""
    category: str
    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0


class ImportedYearInput(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100)
    revenue: float = Field(default=0.0, ge=0)
    ebitda: Optional[float] = None
    depreciation: Optional[float] = Field(default=None, ge=0)
    #: Corporate tax booked for the year. Together with depreciation this is the
    #: closed-book marker: both are year-end entries, and an asset-light trader
    #: that never books depreciation still books its tax at close.
    taxes: Optional[float] = Field(default=None, ge=0)
    cash_and_equivalents: Optional[float] = Field(default=None, ge=0)
    long_term_debt: Optional[float] = Field(default=None, ge=0)
    short_term_financial_debt: Optional[float] = Field(default=None, ge=0)
    trial_balance: List[TrialBalanceEntryInput] = Field(default_factory=list)


class ImportedLedgerAnalysisRequest(BaseModel):
    years: List[ImportedYearInput] = Field(default_factory=list)
    country_code: Optional[str] = "BE"
    nace_code: Optional[str] = None
    industry: Optional[str] = None
    enterprise_value: Optional[float] = None


class PotentialSdeFlag(BaseModel):
    ledger_code: str
    ledger_name: str
    amount: float
    deviation_pct: float
    benchmark_median_pct: float
    benchmark_std_pct: float
    actual_pct_of_revenue: float
    z_score: float
    confidence: float
    year: int
    potential_sde_addback: bool = True
    suggested_question: str
    rationale: str
    category: str
    # Default private-use share (% of the entry amount that is plausibly the
    # owner's personal spending and therefore an SDE add-back). When set the
    # frontend pre-fills a slider so accountants do not have to estimate
    # from zero. Heuristic only — always confirmed by the user.
    default_private_use_pct: Optional[float] = None
    suggested_addback_amount: Optional[float] = None


class EvEquityBridgeResponse(BaseModel):
    #: ``None`` until a real valuation supplies one. The bridge reports the net-debt
    #: position it can actually observe; it never invents an enterprise value.
    enterprise_value: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    long_term_debt: Optional[float] = None
    short_term_financial_debt: Optional[float] = None
    interest_bearing_debt: Optional[float] = None
    net_debt: Optional[float] = None
    equity_value: Optional[float] = None
    #: The fiscal year the balance-sheet cells were read from — always the latest
    #: CLOSED book, never an open one.
    source_fiscal_year: Optional[int] = None
    #: True when every component of net debt was actually present in the ledger.
    #: False means at least one cell was absent, so ``net_debt`` is a partial
    #: observation and the equity figure must not be presented as complete.
    net_debt_complete: bool = False


class DcfDefaultsResponse(BaseModel):
    average_depreciation: float
    suggested_capex: float


class ImportedLedgerYearAnalysis(BaseModel):
    fiscal_year: int
    sde_flags: List[PotentialSdeFlag] = Field(default_factory=list)


class ImportedLedgerAnalysisResponse(BaseModel):
    years: List[ImportedLedgerYearAnalysis] = Field(default_factory=list)
    sde_flags: List[PotentialSdeFlag] = Field(default_factory=list)
    ev_equity_bridge: Optional[EvEquityBridgeResponse] = None
    dcf_defaults: Optional[DcfDefaultsResponse] = None
    latest_fiscal_year: Optional[int] = None
    #: The latest year whose books are actually CLOSED (see ``_year_is_closed``).
    #: Prefer this over ``latest_fiscal_year`` for anything that values, ratios, or
    #: compares periods — ``latest_fiscal_year`` can be an open, part-year book.
    latest_closed_fiscal_year: Optional[int] = None


_BENCHMARKS_BY_PREFIX: Dict[str, Dict[str, float]] = {
    "610": {"median": 3.0, "std": 1.2},
    "611": {"median": 2.6, "std": 1.0},
    "612": {"median": 1.2, "std": 0.5},
    "613": {"median": 1.3, "std": 0.5},
    "614": {"median": 1.8, "std": 0.8},
    "615": {"median": 0.8, "std": 0.4},
    "616": {"median": 1.1, "std": 0.5},
    "617": {"median": 0.7, "std": 0.3},
    "618": {"median": 2.2, "std": 1.0},
    "619": {"median": 1.0, "std": 0.4},
    "620": {"median": 8.0, "std": 2.5},
    "621": {"median": 1.6, "std": 0.7},
    "622": {"median": 2.3, "std": 1.0},
    "623": {"median": 1.0, "std": 0.4},
    "624": {"median": 1.1, "std": 0.5},
    "625": {"median": 0.7, "std": 0.3},
    "626": {"median": 0.8, "std": 0.4},
    "629": {"median": 0.8, "std": 0.4},
    "61": {"median": 11.0, "std": 4.0},
    "62": {"median": 17.0, "std": 5.0},
}


def _expense_amount(entry: TrialBalanceEntryInput) -> float:
    return max(entry.debit - entry.credit, 0.0)


def _normalized_account_code(account_code: str) -> str:
    """Strip provider formatting so MAR prefix rules are stable.

    Mirrors Hermes ``normalized_mar_account_code_prefix``: isolate the leading
    digit run so padded / suffixed GL strings (``620000-ext``, NBSP) still
    classify consistently.
    """
    if not account_code:
        return ""
    s = str(account_code).replace("\ufeff", "").replace("\u00a0", " ").strip()
    s = s.replace(".", "")
    s = "".join(s.split())
    if not s:
        return ""
    end = 0
    while end < len(s) and s[end].isdigit():
        end += 1
    return s[:end] if end > 0 else s


def _is_mar_personnel_social_charges_bucket(account_code: str) -> bool:
    """True for aggregate personnel / social-charges buckets (e.g. 620000).

    Mirrors ``is_mar_owner_director_compensation_account`` in Hermes: Yuki,
    Exact, and Silverfin often label ``620000`` as director pay even though it
    is the normal **personnel massa / sociale lasten** bucket. Flagging the
    full line as an owner-comp add-back is not defensible.
    """
    code = _normalized_account_code(account_code)
    return code.startswith("62000")


def _is_mar_owner_director_compensation_account(account_code: str) -> bool:
    """True for operating owner / director compensation ledger codes.

    ``69xx`` result-appropriation lines are deliberately excluded: even when a
    local chart labels ``695`` as director tantièmes, it sits below net income
    and must not seed an EBITDA/SDE add-back.
    """
    code = _normalized_account_code(account_code)
    if not code:
        return False
    return (
        code.startswith("618")
        or code.startswith("6240")
        or (code.startswith("6200") and not code.startswith("62000"))
    )


def _lookup_benchmark(account_code: str) -> Dict[str, float]:
    for prefix in (account_code[:4], account_code[:3], account_code[:2]):
        if prefix in _BENCHMARKS_BY_PREFIX:
            return _BENCHMARKS_BY_PREFIX[prefix]
    return _BENCHMARKS_BY_PREFIX["61"]


def _question_for_entry(code: str, description: str) -> str:
    label = description.strip() or f"MAR {code}"
    lower = label.lower()
    # MAR 613 — fees to third parties is the classic management-fee conduit
    # used by holding-structure SMEs to channel owner remuneration through a
    # parent vehicle. It must be probed independently from generic 61x.
    if code.startswith("613") or "management fee" in lower or "managementvergoeding" in lower:
        return (
            f"Imported ledger reports {label}. Are these management fees paid to a "
            "related entity (e.g. owner's holding)? If yes, normalize the excess "
            "above an arm's-length replacement-manager cost."
        )
    if code.startswith("611") or "leasing" in lower or "lease" in lower:
        return (
            f"Imported ledger reports {label}. Estimate the private-use share of "
            "this lease (typical owner-vehicle split: 70–100% private). Add back "
            "the private portion to SDE."
        )
    if code.startswith("614") or "auto" in lower or "voertuig" in lower or "brandstof" in lower:
        return (
            f"Imported ledger reports {label}. Estimate the private-use share of "
            "vehicle / fuel costs (typical 50–80% private for owner-managed SMEs)."
        )
    if _is_mar_owner_director_compensation_account(code):
        return (
            f"Imported ledger reports {label}. Is part of this owner compensation "
            "above market and eligible for SDE normalization? Distinguish working-"
            "owner (delta vs. market) from passive-investor (full add-back)."
        )
    if code.startswith("610"):
        return f"Imported ledger reports {label}. Is this related-party rent that should be normalized to market?"
    if code.startswith("615"):
        return (
            f"Imported ledger reports {label}. Are there private travel, lodging "
            "or representation costs to be added back?"
        )
    return f"Imported ledger reports {label}. Should this expense be treated as a discretionary or non-recurring add-back?"


def _category_for_code(code: str) -> str:
    if _is_mar_owner_director_compensation_account(code):
        return "owner_compensation"
    if code.startswith("610"):
        return "related_party_rent"
    if code.startswith("613"):
        return "management_fees"
    if code.startswith(("611", "614", "615")):
        return "discretionary_expense"
    return "operating_expense"


# Default private-use share heuristics for accounts that commonly mix
# business and private spending in owner-managed Belgian SMEs. Surfaced via
# the `default_private_use_pct` field on each flag so the Venus UI can pre-
# fill a slider rather than asking the user to guess from zero.
_DEFAULT_PRIVATE_USE_PCT: Dict[str, float] = {
    "611": 70.0,  # Operationele leasing — owner vehicle predominantly private
    "614": 60.0,  # Vervoerskosten / brandstof — mixed, default 60% private
    "615": 30.0,  # Representatie / reizen — typically partial private
    "619": 20.0,  # Andere diensten en diverse — small private slice
}


def _default_private_use_pct(code: str) -> Optional[float]:
    for prefix in (code[:4], code[:3]):
        if prefix in _DEFAULT_PRIVATE_USE_PCT:
            return _DEFAULT_PRIVATE_USE_PCT[prefix]
    return None


def _benchmark_excess_amount(revenue: float, amount: float, median_pct: float) -> float:
    """Amount above the sector benchmark median expressed as % of revenue."""
    benchmark_amount = revenue * (median_pct / 100.0)
    return max(0.0, round(amount - benchmark_amount, 2))


def _resolve_suggested_addback_amount(
    *,
    amount: float,
    revenue: float,
    median_pct: float,
    default_private: Optional[float],
) -> Optional[float]:
    """Seed auto-normalisations with a defensible default, not the full line."""
    excess = _benchmark_excess_amount(revenue, amount, median_pct)
    if default_private is not None:
        private_use_amount = round(amount * default_private / 100.0, 2)
        return min(private_use_amount, excess) if excess > 0 else private_use_amount
    return excess if excess > 0 else None


def _build_sde_flags(year: ImportedYearInput) -> List[PotentialSdeFlag]:
    if year.revenue <= 0:
        return []

    flags: List[PotentialSdeFlag] = []
    for entry in year.trial_balance:
        code = _normalized_account_code(entry.account_code)
        if not (code.startswith("61") or code.startswith("62")):
            continue
        if _is_mar_personnel_social_charges_bucket(code):
            continue

        amount = _expense_amount(entry)
        if amount <= 0:
            continue

        actual_pct = (amount / year.revenue) * 100.0
        benchmark = _lookup_benchmark(code)
        median_pct = benchmark["median"]
        std_pct = max(benchmark["std"], 0.1)
        threshold = median_pct + 1.5 * std_pct

        if actual_pct < threshold:
            continue

        deviation_pct = actual_pct - median_pct
        z_score = deviation_pct / std_pct
        confidence = min(0.99, 0.55 + max(z_score - 1.5, 0) * 0.12)

        default_private = _default_private_use_pct(code)
        suggested_addback = _resolve_suggested_addback_amount(
            amount=amount,
            revenue=year.revenue,
            median_pct=median_pct,
            default_private=default_private,
        )
        if suggested_addback is None or suggested_addback <= 0:
            continue

        label = entry.description or code
        benchmark_amount = year.revenue * (median_pct / 100.0)
        flags.append(
            PotentialSdeFlag(
                ledger_code=code,
                ledger_name=entry.description or f"MAR {code}",
                amount=round(amount, 2),
                deviation_pct=round(deviation_pct, 2),
                benchmark_median_pct=round(median_pct, 2),
                benchmark_std_pct=round(std_pct, 2),
                actual_pct_of_revenue=round(actual_pct, 2),
                z_score=round(z_score, 2),
                confidence=round(confidence, 2),
                year=year.fiscal_year,
                suggested_question=_question_for_entry(code, entry.description),
                rationale=(
                    f"{label} is {actual_pct:.1f}% of revenue versus a benchmark "
                    f"median of {median_pct:.1f}% (>{threshold:.1f}% threshold). "
                    f"Suggested addback €{int(round(suggested_addback)):,} = excess over "
                    f"benchmark €{int(round(benchmark_amount)):,}."
                ),
                category=_category_for_code(code),
                default_private_use_pct=default_private,
                suggested_addback_amount=suggested_addback,
            )
        )

    flags.sort(key=lambda flag: (flag.year, -flag.deviation_pct, flag.ledger_code))
    return flags


def _year_is_closed(year: ImportedYearInput) -> bool:
    """True when a fiscal year's books look closed rather than mid-flight.

    In Belgian (and most continental) bookkeeping, depreciation and corporate tax
    are year-end closing entries. A book that is still open therefore shows revenue
    and EBITDA but no depreciation and no tax — which is exactly what an eight-month
    trading period looks like when you read it as a completed year: EBIT equals
    EBITDA, equity is last year's carried forward, and every ratio built on it is
    wrong.

    Two markers, either one suffices. Depreciation: a company with fixed assets
    always books it at close. Tax: an asset-light trader never books depreciation
    at all — the first paying advisor's wholesaler is exactly that — but still
    books its corporate tax at close, and an open book shows neither. Tax is
    tested for presence rather than magnitude because a loss-making closed year
    legitimately books zero.
    """
    has_depreciation = year.depreciation is not None and year.depreciation > 0
    has_taxes = year.taxes is not None
    return has_depreciation or has_taxes


def _latest_closed_year(years: List[ImportedYearInput]) -> Optional[ImportedYearInput]:
    """The most recent CLOSED fiscal year, or the most recent year if none qualify.

    The fallback matters for asset-light entities that genuinely book no
    depreciation. Those callers get the old behaviour; the common case — an open
    current year sitting alongside closed history — now resolves to the closed book.
    """
    if not years:
        return None

    closed = [year for year in years if _year_is_closed(year)]
    if closed:
        return max(closed, key=lambda year: year.fiscal_year)
    return max(years, key=lambda year: year.fiscal_year)


def _build_ev_equity_bridge(request: ImportedLedgerAnalysisRequest) -> Optional[EvEquityBridgeResponse]:
    """Report the observable net-debt position of the latest CLOSED book.

    Two rules this function must never break again:

    1. **It does not invent an enterprise value.** It used to fall back to
       ``latest_ebitda * 4.5`` whenever the caller had no valuation yet — which is
       always, at accounting-sync time. That planted a hardcoded, sector-blind,
       size-blind valuation in every client's stored financials and it surfaced to
       advisors as if it were a considered number. When no enterprise value is
       supplied there is no bridge to draw, only a net-debt position.
    2. **A missing balance-sheet cell is unknown, not zero.** Coercing ``None`` to
       ``0.0`` silently reported a company carrying millions in long-term debt as
       debt-free. Absent cells now leave ``net_debt_complete`` False so callers can
       tell "we looked and it was zero" from "we never saw it".
    """
    closed = _latest_closed_year(request.years)
    if closed is None:
        return None

    cash = closed.cash_and_equivalents
    long_term_debt = closed.long_term_debt
    short_term_financial_debt = closed.short_term_financial_debt

    observed = [cash, long_term_debt, short_term_financial_debt]
    net_debt_complete = all(component is not None for component in observed)

    # A partial view still beats no view, but it is labelled as partial.
    interest_bearing_debt = float(long_term_debt or 0.0) + float(short_term_financial_debt or 0.0)
    net_debt = interest_bearing_debt - float(cash or 0.0)

    enterprise_value = request.enterprise_value
    equity_value = None
    if enterprise_value is not None and net_debt_complete:
        equity_value = round(float(enterprise_value) - net_debt, 2)

    return EvEquityBridgeResponse(
        enterprise_value=round(float(enterprise_value), 2) if enterprise_value is not None else None,
        cash_and_equivalents=round(float(cash), 2) if cash is not None else None,
        long_term_debt=round(float(long_term_debt), 2) if long_term_debt is not None else None,
        short_term_financial_debt=(
            round(float(short_term_financial_debt), 2)
            if short_term_financial_debt is not None
            else None
        ),
        interest_bearing_debt=round(interest_bearing_debt, 2),
        net_debt=round(net_debt, 2),
        equity_value=equity_value,
        source_fiscal_year=closed.fiscal_year,
        net_debt_complete=net_debt_complete,
    )


def _build_dcf_defaults(years: List[ImportedYearInput]) -> Optional[DcfDefaultsResponse]:
    depreciation_values = [float(year.depreciation or 0.0) for year in years if (year.depreciation or 0) > 0]
    if not depreciation_values:
        return None
    average_depreciation = round(mean(depreciation_values), 2)
    return DcfDefaultsResponse(
        average_depreciation=average_depreciation,
        suggested_capex=average_depreciation,
    )


@router.post("/imported-ledger", response_model=ImportedLedgerAnalysisResponse)
async def analyze_imported_ledger(
    payload: ImportedLedgerAnalysisRequest,
    _service: ServiceAccount = Depends(require_service_auth),
) -> ImportedLedgerAnalysisResponse:
    years = sorted(payload.years, key=lambda year: year.fiscal_year)
    year_analyses: List[ImportedLedgerYearAnalysis] = []
    all_flags: List[PotentialSdeFlag] = []

    for year in years:
        flags = _build_sde_flags(year)
        year_analyses.append(ImportedLedgerYearAnalysis(fiscal_year=year.fiscal_year, sde_flags=flags))
        all_flags.extend(flags)

    bridge = _build_ev_equity_bridge(payload)
    dcf_defaults = _build_dcf_defaults(years)

    latest_year = years[-1].fiscal_year if years else None
    closed_year_row = _latest_closed_year(years)
    latest_closed_year = closed_year_row.fiscal_year if closed_year_row else None

    logger.info(
        "imported_ledger_analyzed",
        year_count=len(years),
        sde_flag_count=len(all_flags),
        latest_fiscal_year=latest_year,
        latest_closed_fiscal_year=latest_closed_year,
    )

    return ImportedLedgerAnalysisResponse(
        years=year_analyses,
        sde_flags=all_flags,
        ev_equity_bridge=bridge,
        dcf_defaults=dcf_defaults,
        latest_fiscal_year=latest_year,
        latest_closed_fiscal_year=latest_closed_year,
    )
