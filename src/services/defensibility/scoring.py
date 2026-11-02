"""Structured defensibility scoring — academic + ICP scores on a 0-10 scale.

Background
----------
The existing :mod:`classifier` produces a coarse verdict:
``confidence_cap`` (0-1), ``auto_watermark`` (bool), and a free-text list of
``engine_signals``. That is enough to gate the watermark and the asking-price
buffer. It is **not** enough to:

  * answer "should we let the user submit this for an external decision?"
  * tell the user *which input* would most improve the score
  * surface a number on the cover that maps to "how much should I trust this"

This module extends the gate with two structured scores on the 0-10 scale
the strategy doc speaks in (Three Towers Capital: 5/10 ICP, 4.5/10 academic):

  * **Academic score** — does this report meet the standards a competent
    M&A practitioner / Big-4 reviewer would expect? Pillars: methodology
    citations present, all 12 steps executed, real percentile distributions,
    balance sheet provided, owner profile completed, ≥3 years of history.

  * **ICP score** — does this deal fit the Upswitch sweet spot
    (owner-led SME, ≤€10M revenue, supported country, accountant-touched)?
    Below 6/10 means the engine is doing best-effort work outside its
    designed range and the user should know.

Both scores are deterministic, transparently broken down by pillar, and
exposed in the structured :class:`DefensibilityReport` (see :mod:`report`).
The submit-gate uses thresholds on these scores plus the warning severity
list to recommend ALLOW / WARN / BLOCK_SOFT.

We deliberately keep these wrappers — the heavy lifting (years × margin,
engine signals) remains in the existing classifier; this module composes,
it does not duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from src.config.countries import SUPPORTED_COUNTRIES
from src.services.defensibility.methodology import (
    Methodology,
    has_own_confidence_framework,
)
from src.services.defensibility.warning_signal_detection import resolve_years_of_data

# ---------------------------------------------------------------------------
# Score primitives
# ---------------------------------------------------------------------------


class ScoreBand(Enum):
    """Coarse band a 0-10 score lands in. Drives chip color."""

    EXCELLENT = "excellent"  # 9-10
    STRONG = "strong"  # 7-8
    ADEQUATE = "adequate"  # 5-6
    WEAK = "weak"  # 3-4
    INSUFFICIENT = "insufficient"  # 0-2

    @classmethod
    def from_score(cls, score: int) -> "ScoreBand":
        if score >= 9:
            return cls.EXCELLENT
        if score >= 7:
            return cls.STRONG
        if score >= 5:
            return cls.ADEQUATE
        if score >= 3:
            return cls.WEAK
        return cls.INSUFFICIENT


@dataclass(frozen=True)
class ScorePillar:
    """One contributing factor in a 0-10 composite score.

    ``points_earned`` and ``points_possible`` always satisfy
    ``0 <= points_earned <= points_possible``. The pillar name is the
    machine-readable code; the description is the human-readable rationale
    surfaced in the report.
    """

    code: str
    description: str
    points_earned: int
    points_possible: int

    @property
    def is_full_credit(self) -> bool:
        return self.points_earned == self.points_possible


@dataclass(frozen=True)
class CompositeScore:
    """A 0-10 score with per-pillar breakdown.

    Frozen by design: the score is computed once per request and read by
    the report renderer, the cover chip, and the submit gate. Any of those
    consumers mutating the score would create cross-cutting drift.
    """

    score: int  # 0-10 — round half up of the pillar sum, capped at 10
    pillars: List[ScorePillar]
    band: ScoreBand
    # Set ONLY when the scorer itself raised and the caller substituted a
    # fallback. ``None`` on every genuinely computed score, including a real
    # measured 0/10. Consumers MUST read ``error is not None`` as "not
    # measured" rather than "measured and bad" — a 0 with an error marker is a
    # bug in our plumbing, not a judgement about the customer's deal.
    error: Optional[str] = None

    @property
    def total_possible(self) -> int:
        return sum(p.points_possible for p in self.pillars)

    @property
    def total_earned(self) -> int:
        return sum(p.points_earned for p in self.pillars)


# ---------------------------------------------------------------------------
# Helpers (intentionally narrow — defensive against missing fields)
# ---------------------------------------------------------------------------


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return int(Decimal(str(value)))
        except (ValueError, ArithmeticError):
            return default


def _safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return default


def _years_of_data(valuation_data: Dict[str, Any]) -> int:
    """Delegates to the single canonical resolver — see warning_signal_detection.

    Kept as a thin alias so existing call sites and tests in this module do not
    all have to move at once.
    """
    return resolve_years_of_data(valuation_data)


def _balance_sheet_provided(valuation_data: Dict[str, Any]) -> bool:
    """True iff cash OR debt is non-zero, OR metadata explicitly flags it."""
    metadata = valuation_data.get("metadata")
    if isinstance(metadata, dict) and metadata.get("balance_sheet_provided"):
        return True
    cur = valuation_data.get("current_year_data")
    if not isinstance(cur, dict):
        return False
    cash = _safe_decimal(cur.get("cash"))
    debt = _safe_decimal(cur.get("total_debt"))
    return cash != 0 or debt != 0


def _has_real_percentiles(valuation_data: Dict[str, Any]) -> bool:
    """True iff multiple percentiles came from a market source, not synthetic.

    The collector tags the source. ``synthetic_20pct`` means we fabricated
    p25/p75 by widening p50 ±20% — fine for a calculation but not the
    Damodaran-grade evidence a Big-4 reviewer expects.
    """
    detailed = valuation_data.get("detailed_results")
    if not isinstance(detailed, dict):
        detailed = valuation_data
    src = (
        detailed.get("ev_ebitda_percentile_source")
        or detailed.get("ev_revenue_percentile_source")
        or ""
    )
    return isinstance(src, str) and src == "market_derived"


def _owner_profile_completed(valuation_data: Dict[str, Any]) -> bool:
    odr = valuation_data.get("owner_dependency_result")
    if not isinstance(odr, dict):
        return False
    # The synthesizer always sets risk_level when the assessment ran.
    risk = odr.get("risk_level")
    return isinstance(risk, str) and risk.strip() != ""


def _all_steps_completed_cleanly(valuation_data: Dict[str, Any]) -> bool:
    """True iff no step downgraded with degraded inputs.

    The orchestrator marks degraded execution in the transparency report;
    we look for the absence of step-level WARN markers on the response.
    Best-effort: missing structure → assume not all clean.
    """
    transparency = valuation_data.get("transparency_report")
    if not isinstance(transparency, dict):
        return False
    steps = transparency.get("calculation_steps")
    if not isinstance(steps, list) or not steps:
        return False
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("status") not in (None, "COMPLETED", "completed"):
            return False
        if step.get("execution_quality") in ("degraded", "partial"):
            return False
    return True


# ICP revenue design band. Named constants rather than literals inside the
# predicate: widening this band is a live product decision, so it must be a
# one-line change that tests can assert against.
ICP_REVENUE_FLOOR: Decimal = Decimal("100000")  # €100K
ICP_REVENUE_CEILING: Decimal = Decimal("10000000")  # €10M


def _supported_country(country_code: Any) -> bool:
    """True for the Upswitch Index review-coverage markets.

    Reads the canonical list from :mod:`src.config.countries` instead of
    re-declaring it. The previous inline set held 16 codes and omitted ``IE``,
    so every Irish company scored 0/2 on this pillar while Mercury, Titan and
    Delphi all treated Ireland as product-exposed. Note this pillar asks
    "is this deal inside our design range", not "how good is our data there" —
    per-country data fidelity is already disclosed separately via
    ``country_confidence_tier``.
    """
    if not isinstance(country_code, str) or len(country_code.strip()) != 2:
        return False
    return country_code.strip().upper() in SUPPORTED_COUNTRIES


def _revenue_in_sme_band(revenue: Decimal) -> bool:
    """ICP target: €100K–€10M revenue (see the module constants above)."""
    return ICP_REVENUE_FLOOR <= revenue <= ICP_REVENUE_CEILING


# Actor roles that constitute professional preparation for ICP purposes.
# Mirrors Titan's ``ACCOUNTANT_ROLES`` (accountant / expert / enterprise are
# the three accountant tiers — see
# ``apps/titan-api/src/auth/constants/roles.constants.ts``). Deliberately
# NARROWER than ``report_audience_context._ADVISOR_ROLES``, which also holds
# "buyer" and "admin": those describe who the report is *for* or who operated
# the console, not evidence that a qualified preparer touched the numbers.
_ACCOUNTANT_ROLE_VALUES = frozenset({"accountant", "expert", "enterprise"})


def _accountant_signal(valuation_data: Dict[str, Any]) -> Optional[bool]:
    """Tri-state: True touched, False measured-and-self-served, None unmeasured.

    Trust-node primitive: accountant-delivered = higher ICP fit.

    Signals, in the order the platform actually stamps them:

      * ``accountant_id`` / ``created_by_role`` — legacy aggregator stamp.
      * ``metadata.actor_role`` — the role of the user who ran the valuation.
        This is what Titan sends today. Until this branch existed, every
        accountant-run report scored 0 on this pillar and told a paying
        accountant they were "self-served".
      * ``metadata.accountant_customer_id`` — present only when the run was
        bound to an accountant's client record, so its presence alone proves
        the relationship (same read as
        ``report_audience_context._has_accountant_customer``).
      * ``metadata.report_commissioned_audience == "advisor"`` — the
        COMMISSIONED audience, an explicit Titan stamp. Deliberately NOT the
        derived context key ``report_audience``:
        ``resolve_report_audience_from_metadata`` defaults to "advisor"
        whenever metadata is missing or unrecognised, so trusting the derived
        value would hand 2 free points to every self-served report and make
        this pillar a constant.

    ``None`` is returned when the payload carries no preparer-identity surface
    at all — we then know nothing, which is not the same as knowing the report
    was self-served.
    """
    if valuation_data.get("accountant_id"):
        return True
    role = valuation_data.get("created_by_role")
    if isinstance(role, str) and role.strip().lower() in _ACCOUNTANT_ROLE_VALUES:
        return True

    metadata = valuation_data.get("metadata")
    if not isinstance(metadata, dict):
        # No identity surface anywhere on the payload → unmeasured.
        return None if role is None else False

    if metadata.get("accountant_id") or metadata.get("accountant_email"):
        return True
    if metadata.get("accountant_customer_id") or metadata.get("accountantCustomerId"):
        return True

    actor_role = metadata.get("actor_role") or metadata.get("actorRole")
    if isinstance(actor_role, str) and actor_role.strip().lower() in _ACCOUNTANT_ROLE_VALUES:
        return True

    # Deliberately NOT consulted: `report_commissioned_audience`. The docstring
    # above once trusted it as "an explicit Titan stamp", but Titan's
    # `resolve-report-audience.util.ts` resolves it as
    # `metadata.report_commissioned_audience ?? metadata.report_audience ?? 'advisor'`
    # and `buildReportAudienceMetadataFields` writes that resolved value back —
    # so a payload with no audience signal at all arrives stamped "advisor".
    # Trusting it would hand 2 free points to every self-served report, the
    # same constant-pillar failure the docstring warns about for the derived key.
    # `actor_role` and `accountant_customer_id` are real observations; this is not.

    # Metadata exists and names an actor, so "not an accountant" is a real
    # observation. Metadata exists but names nobody → still unmeasured.
    if actor_role or metadata.get("actor_user_id") or metadata.get("actorUserId"):
        return False
    return None


def _accountant_touched(valuation_data: Dict[str, Any]) -> bool:
    """Boolean shim over :func:`_accountant_signal` — unknown reads as False.

    Scoring itself uses the tri-state so it can distinguish "no accountant"
    from "we never looked".
    """
    return _accountant_signal(valuation_data) is True


def _owner_led_signal(valuation_data: Dict[str, Any]) -> Optional[bool]:
    """Tri-state owner-led read: True / False / None when never supplied.

    ICP target: >=1 owner-manager AND <=10 FTE (the SDE / owner-first sweet
    spot). The predicate needs BOTH counts, so if either is absent the fit is
    unknown — returning False there would assert "not owner-led" about a
    company we never measured, which is exactly the false negative this pillar
    was printing on paying customers' reports.

    Note the ``is None`` fallbacks rather than ``or``: an explicit zero is a
    measurement and must not fall through to the metadata copy.
    """
    metadata = valuation_data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    raw_owners = valuation_data.get("owner_managers")
    if raw_owners is None:
        raw_owners = metadata.get("owner_managers")
    raw_ftes = valuation_data.get("total_employees")
    if raw_ftes is None:
        raw_ftes = metadata.get("total_employees")
    if raw_owners is None or raw_ftes is None:
        return None
    owners = _safe_decimal(raw_owners)
    ftes = _safe_decimal(raw_ftes)
    return owners >= Decimal("1") and Decimal("0") < ftes <= Decimal("10")


def _is_owner_led_sme(valuation_data: Dict[str, Any]) -> bool:
    """Boolean shim over :func:`_owner_led_signal` — unknown reads as False."""
    return _owner_led_signal(valuation_data) is True


# ---------------------------------------------------------------------------
# Academic score — Big-4 reviewer perspective
# ---------------------------------------------------------------------------


def compute_academic_score(
    valuation_data: Dict[str, Any], methodology: Methodology
) -> CompositeScore:
    """Compute the 0-10 academic defensibility score.

    Pillars (total 10 pts):
      * Methodology has documented academic citations — 2 pts
        (proxy: methodology recognized + not UNKNOWN)
      * All 12 steps executed without degradation — 2 pts
      * Multiple percentiles from real comparables — 2 pts
        (skipped for STARTUP / ASSET — they don't use multiples)
      * Balance sheet provided + reconciled — 1 pt
        (skipped for STARTUP — pre-revenue)
      * Owner Profile (12-factor) completed — 1 pt
        (skipped for STARTUP / ASSET / DCF — methodology-gated)
      * ≥3 years of historical data — 2 pts
        (skipped for STARTUP — 0 years is the premise)

    For methodology-gated pillars, the points-possible is reduced; the
    final score is rescaled to 0-10 so a startup with full credit on its
    applicable pillars still scores 10/10.
    """
    pillars: List[ScorePillar] = []

    # 1. Methodology recognition + citations
    methodology_recognized = methodology != Methodology.UNKNOWN
    pillars.append(
        ScorePillar(
            code="methodology_citations",
            description=(
                "Methodology recognized with documented academic citations"
                if methodology_recognized
                else "Methodology unrecognized — no citation backing"
            ),
            points_earned=2 if methodology_recognized else 0,
            points_possible=2,
        )
    )

    # 2. All 12 steps clean (skipped for STARTUP — they bypass the 12-step path)
    if methodology != Methodology.STARTUP:
        clean = _all_steps_completed_cleanly(valuation_data)
        pillars.append(
            ScorePillar(
                code="steps_clean",
                description=(
                    "All calculation steps completed without degradation"
                    if clean
                    else "One or more steps degraded — review transparency report"
                ),
                points_earned=2 if clean else 0,
                points_possible=2,
            )
        )

    # 3. Real percentile distributions (skipped for STARTUP / ASSET)
    if methodology not in (Methodology.STARTUP, Methodology.ASSET):
        real_pct = _has_real_percentiles(valuation_data)
        pillars.append(
            ScorePillar(
                code="market_percentiles",
                description=(
                    "Multiple percentiles derived from real market comparables"
                    if real_pct
                    else "Synthetic percentiles (±20% around the median) — Damodaran "
                    "p25/p75 not available for this cell"
                ),
                points_earned=2 if real_pct else 0,
                points_possible=2,
            )
        )

    # 4. Balance sheet (skipped for STARTUP — pre-revenue)
    if methodology != Methodology.STARTUP:
        bs = _balance_sheet_provided(valuation_data)
        pillars.append(
            ScorePillar(
                code="balance_sheet",
                description=(
                    "Balance sheet data provided"
                    if bs
                    else "No balance sheet — net-debt assumed zero"
                ),
                points_earned=1 if bs else 0,
                points_possible=1,
            )
        )

    # 5. Owner Profile (only when methodology runs the 12-factor adjustment)
    if methodology in (Methodology.MULTIPLES, Methodology.HYBRID, Methodology.SDE):
        op = _owner_profile_completed(valuation_data)
        pillars.append(
            ScorePillar(
                code="owner_profile",
                description=(
                    "Owner Profile (12-factor transferability) completed"
                    if op
                    else "Owner Profile not completed — transferability risk unquantified"
                ),
                points_earned=1 if op else 0,
                points_possible=1,
            )
        )

    # 6. Historical data depth (skipped for STARTUP)
    if methodology != Methodology.STARTUP:
        years = _years_of_data(valuation_data)
        if years >= 3:
            pts = 2
            desc = f"{years} years of historical data (≥3 required for full credit)"
        elif years == 2:
            pts = 1
            desc = "2 years of historical data — partial credit; ≥3 preferred"
        else:
            pts = 0
            desc = f"{years} year(s) of historical data — insufficient for full credit"
        pillars.append(
            ScorePillar(
                code="historical_depth",
                description=desc,
                points_earned=pts,
                points_possible=2,
            )
        )

    total_earned = sum(p.points_earned for p in pillars)
    total_possible = sum(p.points_possible for p in pillars) or 10
    # Rescale to 0-10 (so methodology-gated pillars don't penalize unfairly).
    score = int(round((total_earned / total_possible) * 10))
    score = max(0, min(10, score))
    return CompositeScore(score=score, pillars=pillars, band=ScoreBand.from_score(score))


# ---------------------------------------------------------------------------
# ICP score — does this deal fit Upswitch's design range?
# ---------------------------------------------------------------------------


def compute_icp_score(valuation_data: Dict[str, Any], methodology: Methodology) -> CompositeScore:
    """Compute the 0-10 ICP (Ideal Customer Profile) fit score.

    Five 2-point pillars (total 10 pts):
      * Revenue in €100K–€10M SME band — 2 pts
      * Country in the supported Upswitch Index markets — 2 pts
      * Business type recognized in our 183-type catalog — 2 pts
      * Owner-led / sole-trader profile (≤10 FTE) — 2 pts
      * Accountant-touched (created or reviewed by accountant) — 2 pts

    Below 6/10 means the engine is operating outside its designed range
    and the user should be told. STARTUP / ASSET methodologies still get
    scored — owner-led, country, and BT pillars apply universally.
    """
    pillars: List[ScorePillar] = []

    # 1. Revenue band
    revenue = _safe_decimal(valuation_data.get("revenue"))
    if revenue == 0:
        cur = valuation_data.get("current_year_data") or {}
        if isinstance(cur, dict):
            revenue = _safe_decimal(cur.get("revenue"))
    in_band = _revenue_in_sme_band(revenue)
    pillars.append(
        ScorePillar(
            code="revenue_band",
            description=(
                f"Revenue €{int(revenue):,} fits SME design band (€100K–€10M)"
                if in_band
                else f"Revenue €{int(revenue):,} outside SME design band (€100K–€10M)"
            ),
            points_earned=2 if in_band else 0,
            points_possible=2,
        )
    )

    # 2. Country
    country = valuation_data.get("country_code") or valuation_data.get("country") or ""
    in_country = _supported_country(country)
    pillars.append(
        ScorePillar(
            code="country_supported",
            description=(
                f"Country {str(country).upper()} in the supported Upswitch Index markets"
                if in_country
                else f"Country {country!r} outside the supported Upswitch Index markets"
            ),
            points_earned=2 if in_country else 0,
            points_possible=2,
        )
    )

    # 3. Business type recognized
    bt_id = valuation_data.get("business_type_id")
    bt_recognized = isinstance(bt_id, str) and bt_id.strip() != ""
    pillars.append(
        ScorePillar(
            code="business_type_recognized",
            description=(
                f"Business type '{bt_id}' recognized in catalog"
                if bt_recognized
                else "No business_type_id — falling back to industry/category"
            ),
            points_earned=2 if bt_recognized else 0,
            points_possible=2,
        )
    )

    # 4. Owner-led profile
    owner_led = _owner_led_signal(valuation_data)
    if owner_led is True:
        owner_led_description = "Owner-led SME (≥1 owner, ≤10 FTE) — Upswitch sweet spot"
    elif owner_led is False:
        owner_led_description = "Not owner-led — engine designed for owner-operated SMEs"
    else:
        # Never assert a negative we did not measure. No owner-manager or FTE
        # count reached the scorer, so the fit is unknown, not disproved.
        owner_led_description = (
            "Owner-manager and FTE count not supplied — owner-led fit not assessed"
        )
    pillars.append(
        ScorePillar(
            code="owner_led_profile",
            description=owner_led_description,
            points_earned=2 if owner_led is True else 0,
            points_possible=2,
        )
    )

    # 5. Accountant-touched
    accountant = _accountant_signal(valuation_data)
    if accountant is True:
        accountant_description = "Created or reviewed by an accountant"
    elif accountant is False:
        accountant_description = "Self-served — no accountant validation"
    else:
        # The payload carried no preparer identity at all. Saying "self-served"
        # here is a claim we cannot support, and it is exactly what a paying
        # accountant saw printed on their own report.
        accountant_description = (
            "Preparer identity not recorded on this report — accountant "
            "involvement not assessed"
        )
    pillars.append(
        ScorePillar(
            code="accountant_touched",
            description=accountant_description,
            points_earned=2 if accountant is True else 0,
            points_possible=2,
        )
    )

    total_earned = sum(p.points_earned for p in pillars)
    score = max(0, min(10, total_earned))
    return CompositeScore(score=score, pillars=pillars, band=ScoreBand.from_score(score))
