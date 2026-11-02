"""Pydantic v2 input contract for the startup valuation engine."""

from decimal import Decimal
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

StartupStage = Literal["pre_seed", "seed", "series_a"]

#: Founder-pickable sector key.  Drives smart defaults for the VC Method's
#: exit revenue multiple and (later) the regional comparable set.  See
#: ``regional_data.SECTOR_DEFAULTS`` for the actual numbers.
StartupSector = Literal[
    "saas",
    "marketplace",
    "fintech",
    "biotech_healthtech",
    "deeptech_ai",
    # Vertical-AI workflow plays (Casetext / Harvey / AlphaSense lane):
    # AI-native software that owns a workflow end-to-end with a
    # proprietary data flywheel.  Distinct from ``deeptech_ai`` (which
    # captures research-led AI / foundational-model R&D); ``vertical_ai``
    # is the application-layer category where defensibility comes from
    # owning the integration surface + the training-data exhaust, not
    # from raw model performance.  Commands a premium on Y5 exit
    # multiple (~10×) vs generic SaaS (6×) because vertical-AI exits
    # in 2023-2026 (Casetext / Harvey / AlphaSense / Hebbia) repeatedly
    # cleared that band.
    "vertical_ai",
    "consumer",
    "hardware",
    "other",
]

RoundInstrument = Literal[
    "priced_equity",
    "safe",
    "convertible_note",
    "kiss",
    "other",
]

RoundStatus = Literal[
    "draft_scenario",
    "active_round",
    "committed",
    "closed",
    "stale_expired",
]

RoundEvidenceSource = Literal[
    "founder_entered",
    "signed_term_sheet",
    "investor_commitment",
    "market_benchmark",
    "advisor_entered",
    "engine_calculation",
]

RoundEvidenceQuality = Literal[
    "unverified",
    "founder_asserted",
    "documented",
    "signed",
    "market_confirmed",
]

RoundValueRelationship = Literal[
    "model_derived_valuation",
    "market_implied_valuation",
    "blended_weighted_view",
]

StartupBenchmarkSourceType = Literal[
    "local_market_average",
    "comparable_round",
    "announced_round",
    "signed_term_sheet",
    "advisor_entered",
    "founder_entered",
]

StartupBenchmarkEvidenceQuality = Literal[
    "public_source",
    "announced_round",
    "signed_term_sheet",
    "advisor_entered",
    "founder_entered",
    "local_market_average",
    "inferred",
]

StartupBenchmarkGeographyScope = Literal[
    "city",
    "country",
    "benelux",
    "eu",
    "international",
]

LifecycleStageCandidate = Literal[
    "pre_revenue",
    "early_revenue",
    "seed",
    "growth",
    "growth_startup",
    "mature",
    "transition",
    "unknown",
]

LifecycleRevenueState = Literal[
    "none",
    "first_revenue",
    "recurring_revenue",
    "mature_revenue",
    "unknown",
]

LifecycleConfidenceLevel = Literal["low", "medium", "high"]

#: Inception-lens — opt-in overlay that acknowledges three pre-seed
#: realities the milestone-track methods (Berkus / Scorecard) systematically
#: miss:
#:
#:   1. Moats don't exist yet at inception — momentum is oxygen, moat is
#:      a consequence (cf. Google's data flywheel built *after* takeoff).
#:   2. TAM is unknowable at inception — the best founders create markets
#:      that don't exist (Shopify '08, Veeva, Uber, Airbnb were all "TAM
#:      too small" passes that returned 100×+).
#:   3. Edge founders cost more — paying $30M post for 2% of a Lovable /
#:      Anthropic / Cursor profile is a defensible bet shape.
#:
#: Three levels:
#:
#:   * ``milestones_driven`` (default) — standard pre-seed weighting; no
#:     overlay.  Right for the median founder with measurable milestones.
#:   * ``momentum_driven`` — multiplier 1.10× on the leg-blend baseline,
#:     band widened ±15%.  For founders with tangible momentum signals
#:     (inbound investor interest, hiring acceleration, early customer
#:     pull) but no spike profile yet.
#:   * ``inception_bet`` — multiplier 1.25× on the leg-blend baseline,
#:     band widened ±25%.  For the Lovable / Anthropic / Cursor profile:
#:     spike technical / distribution / product profile, market-creating
#:     thesis, generational ambition.  Variance is high, expected value
#:     is asymmetric — engine acknowledges both directions explicitly
#:     by widening the equity_low / equity_high band.
InceptionLens = Literal[
    "milestones_driven",
    "momentum_driven",
    "inception_bet",
]


class SafeNote(BaseModel):
    """A single SAFE / convertible note on the cap table."""

    amount: Decimal = Field(..., ge=Decimal("0"), description="Principal amount in EUR")
    valuation_cap: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Valuation cap in EUR (None = uncapped)"
    )
    discount_pct: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Conversion discount percentage (0-100)",
    )
    holder_label: Optional[str] = Field(
        None, max_length=120, description="Optional investor / round label"
    )


class RoundScenario(BaseModel):
    """A fundraising round/cap scenario used as startup valuation evidence.

    This object is deliberately not the objective valuation itself. It is
    market-implied evidence that can be compared with the engine-derived
    startup dot while keeping provenance visible.
    """

    label: Optional[str] = Field(None, max_length=120)
    pre_money: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Round pre-money valuation in EUR"
    )
    post_money: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Round post-money valuation in EUR"
    )
    valuation_cap: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="SAFE/convertible valuation cap in EUR"
    )
    target_amount: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Target raise amount in EUR"
    )
    amount_raised: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Committed or raised amount in EUR"
    )
    instrument_type: RoundInstrument = Field("priced_equity")
    discount_pct: Optional[Decimal] = Field(
        None, ge=Decimal("0"), le=Decimal("100"), description="Convertible discount percentage"
    )
    target_close_date: Optional[str] = Field(
        None, max_length=20, description="ISO date (YYYY-MM-DD) target close date"
    )
    status: RoundStatus = Field("draft_scenario")
    evidence_source: RoundEvidenceSource = Field("founder_entered")
    evidence_quality: RoundEvidenceQuality = Field("founder_asserted")
    value_relationship: RoundValueRelationship = Field("market_implied_valuation")
    assumptions: Dict[str, object] = Field(
        default_factory=dict,
        description="Scenario assumptions that explain this market-implied layer",
    )

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _derive_missing_pre_or_post_money(self) -> "RoundScenario":
        amount = self.amount_raised if self.amount_raised is not None else self.target_amount
        if amount is None:
            return self
        if self.post_money is None and self.pre_money is not None:
            object.__setattr__(self, "post_money", self.pre_money + amount)
        elif self.pre_money is None and self.post_money is not None and self.post_money >= amount:
            object.__setattr__(self, "pre_money", self.post_money - amount)
        return self


class StartupBenchmarkInput(BaseModel):
    """One startup benchmark observation supplied by Delphi, Athena, or a user.

    Local-average rows can calibrate the regional reference anchor. Company-
    specific rounds, caps, and SAFEs are evidence layers only: they explain
    market context but do not overwrite the objective engine dot.
    """

    source_type: StartupBenchmarkSourceType = Field("local_market_average")
    evidence_quality: StartupBenchmarkEvidenceQuality = Field("local_market_average")
    value_relationship: RoundValueRelationship = Field("market_implied_valuation")

    geography_scope: StartupBenchmarkGeographyScope = Field("country")
    geography_label: Optional[str] = Field(None, max_length=120)
    city_name: Optional[str] = Field(None, max_length=120)
    country_code: Optional[str] = Field(None, pattern="^[A-Z]{2}$")
    region_code: Optional[str] = Field(None, max_length=30)
    stage: Optional[StartupStage] = None
    sector: Optional[StartupSector] = None

    average_pre_money_eur: Optional[Decimal] = Field(None, ge=Decimal("0"))
    p25_pre_money_eur: Optional[Decimal] = Field(None, ge=Decimal("0"))
    p75_pre_money_eur: Optional[Decimal] = Field(None, ge=Decimal("0"))
    pre_money_eur: Optional[Decimal] = Field(None, ge=Decimal("0"))
    post_money_eur: Optional[Decimal] = Field(None, ge=Decimal("0"))
    valuation_cap_eur: Optional[Decimal] = Field(None, ge=Decimal("0"))
    amount_raised_eur: Optional[Decimal] = Field(None, ge=Decimal("0"))
    discount_pct: Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("100"))

    exit_multiple_low: Optional[Decimal] = Field(None, ge=Decimal("0"))
    exit_multiple_high: Optional[Decimal] = Field(None, ge=Decimal("0"))
    sample_size: Optional[int] = Field(None, ge=0)

    source: str = Field(..., max_length=240)
    source_url: Optional[str] = Field(None, max_length=500)
    observed_at: Optional[str] = Field(None, max_length=20)
    methodology_version: Optional[str] = Field(None, max_length=80)
    notes: Optional[str] = Field(None, max_length=500)

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _derive_post_money_from_pre_money_and_amount(self) -> "StartupBenchmarkInput":
        if (
            self.post_money_eur is None
            and self.pre_money_eur is not None
            and self.amount_raised_eur is not None
        ):
            object.__setattr__(
                self,
                "post_money_eur",
                self.pre_money_eur + self.amount_raised_eur,
            )
        return self


class LifecycleSignalProvenance(BaseModel):
    """One classified lifecycle signal with source/provenance attached."""

    signal: str = Field(..., max_length=80)
    source: str = Field(..., max_length=120)
    value: Optional[object] = None
    reason: Optional[str] = Field(None, max_length=280)
    confidence: LifecycleConfidenceLevel = Field("medium")

    model_config = ConfigDict(extra="ignore")


class LifecycleStageTriage(BaseModel):
    """Company-stage intelligence beside the business-type taxonomy.

    ``business_type_tags`` answer what the company is. The lifecycle stage
    answers which valuation logic is allowed. Keeping them separate prevents
    startup-shaped companies from silently falling into mature-SME methods.
    """

    business_type_tags: List[str] = Field(default_factory=list, max_length=24)
    lifecycle_stage_candidate: LifecycleStageCandidate = Field("unknown")
    startup_signal_confidence: int = Field(0, ge=0, le=100)
    confidence_level: LifecycleConfidenceLevel = Field("low")
    revenue_state: LifecycleRevenueState = Field("unknown")
    classification_reasons: List[str] = Field(default_factory=list, max_length=16)
    missing_evidence_questions: List[str] = Field(default_factory=list, max_length=8)
    signal_provenance: List[LifecycleSignalProvenance] = Field(
        default_factory=list,
        max_length=32,
    )
    geography_cluster: Optional[str] = Field(None, max_length=80)
    manual_override_provenance: Dict[str, object] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _sync_confidence_level(self) -> "LifecycleStageTriage":
        if self.startup_signal_confidence >= 75:
            level: LifecycleConfidenceLevel = "high"
        elif self.startup_signal_confidence >= 50:
            level = "medium"
        else:
            level = "low"
        object.__setattr__(self, "confidence_level", level)
        return self


class FounderPedigreeInputs(BaseModel):
    """Founder-team qualifications driving the pedigree multiplier.

    Each flag is a discrete, defensible claim — the deliberate absence of
    a free-form slider is the design choice: the multiplier only moves when
    the founder picks a specific, verifiable qualification. See
    :mod:`.founder_pedigree` for the deltas, calibration sources, and the
    multiplicative overlay applied on top of the synthesis blend.
    """

    prior_exit: bool = Field(
        False, description="Any cofounder has exited a venture-backed company at >=€10M"
    )
    top_unicorn_alumnus: bool = Field(
        False,
        description=(
            "Any cofounder is a senior alumnus (>=2 years, IC4+ equivalent) of a top-tier "
            "scaleup (Adyen, Showpad, Collibra, Bol, Mollie, UiPath, Klarna, Wise, etc.)"
        ),
    )
    domain_expert_10y: bool = Field(
        False, description="Any cofounder has 10+ years experience in the target industry"
    )
    second_time_founder: bool = Field(
        False, description="Any cofounder previously founded a company that ran >=2 years"
    )
    has_technical_cofounder: bool = Field(
        False, description="At least one full-time technical cofounder owns the codebase"
    )
    solo_founder: bool = Field(False, description="Single founder, no cofounders (penalty applied)")

    # ---- Evidence gate ---------------------------------------------------
    # The pedigree multiplier is unverifiable on its own — a founder can
    # tick "prior_exit" without any way to defend it in front of a partner.
    # This optional dict carries one short evidence string per claimed
    # positive delta (LinkedIn URL, KBO incorporation reference, named
    # employer + tenure, etc.).  When a positive delta is claimed *without*
    # a corresponding non-empty evidence string, the engine zeros that
    # delta — the negative ``solo_founder`` delta is never gated.
    #
    # Keys must match the boolean field names above.  Extra keys are
    # ignored.  Empty / whitespace-only strings count as missing.
    pedigree_evidence: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional per-claim evidence strings (LinkedIn URL, KBO "
            "reference, etc.).  Positive pedigree deltas without a "
            "non-empty evidence string are zeroed by the engine."
        ),
    )

    @model_validator(mode="after")
    def _solo_founder_excludes_technical_cofounder(self) -> "FounderPedigreeInputs":
        """Solo + technical-cofounder is a contradiction — quietly resolve.

        Picking the solo flag explicitly forbids the technical-cofounder
        lift; if the founder accidentally toggled both, we drop the
        positive flag rather than rejecting the whole payload (the UI
        already enforces this but the engine should never trust the UI).
        """
        if self.solo_founder and self.has_technical_cofounder:
            object.__setattr__(self, "has_technical_cofounder", False)
        return self

    @model_validator(mode="after")
    def _bound_pedigree_evidence(self) -> "FounderPedigreeInputs":
        """Defensive bounds on the open-keyed evidence dict.

        ``Dict[str, str]`` is unbounded by default — a hostile or buggy
        client could inject hundreds of keys with megabyte-long values,
        blowing up the JSON payload + every PDF render that surfaces the
        evidence text in the defensibility table.  Two-line defence:

        1. Cap the dict at ``_MAX_PEDIGREE_EVIDENCE_KEYS`` entries —
           more than the canonical claim count is by definition junk.
        2. Cap each value at ``_MAX_PEDIGREE_EVIDENCE_LEN`` characters —
           one short sentence is plenty; longer is not more credible.

        We *truncate* rather than reject because the engine prefers
        graceful degradation here: an evidence string that's too long
        still indicates the founder engaged with the gate, and the
        truncated text remains useful in the report.  Empty / non-string
        values are dropped silently.
        """
        evidence = self.pedigree_evidence or {}
        if not evidence:
            return self
        bounded: Dict[str, str] = {}
        for i, (key, value) in enumerate(evidence.items()):
            if i >= _MAX_PEDIGREE_EVIDENCE_KEYS:
                break
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            trimmed = value.strip()[:_MAX_PEDIGREE_EVIDENCE_LEN]
            if trimmed:
                bounded[key] = trimmed
        object.__setattr__(self, "pedigree_evidence", bounded)
        return self


# Bounds tuned to the natural shape of the data: six possible claims,
# one short LinkedIn-URL-or-sentence per claim.  Generous headroom on
# the key count so a UI bug that double-keys an entry doesn't bite.
_MAX_PEDIGREE_EVIDENCE_KEYS: int = 12
_MAX_PEDIGREE_EVIDENCE_LEN: int = 500  # mirrors the frontend textarea ``maxLength=500``


class CapTableSummary(BaseModel):
    """High-level cap-table summary supplied by the founder."""

    pre_money_target: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Founder's target pre-money valuation for the next round (EUR)",
    )
    option_pool_pct: Decimal = Field(
        Decimal("0"),
        ge=Decimal("0"),
        le=Decimal("50"),
        description="Option pool reserved (post-round) as percentage of fully-diluted shares",
    )
    safe_notes: List[SafeNote] = Field(
        default_factory=list, max_length=20, description="Outstanding SAFE / convertible notes"
    )
    last_round_amount: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Amount raised in the last round (EUR)"
    )
    last_round_post_money: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Post-money valuation of the last round (EUR)"
    )
    last_round_date: Optional[str] = Field(
        None, max_length=20, description="ISO date (YYYY-MM-DD) of the last round"
    )


class StartupInputs(BaseModel):
    """Founder-supplied data for the startup valuation engine.

    All fields are optional individually; the engine defends against
    missing data with stage-specific defaults so that a pre-seed founder
    can still get a defensible range with the bare minimum filled in.
    """

    # --- Stage / context ---
    stage: StartupStage = Field("seed", description="Funding stage")
    country_code: str = Field("BE", pattern="^[A-Z]{2}$", description="ISO country code")
    nace_code: Optional[str] = Field(None, max_length=20)
    sector: StartupSector = Field(
        "saas",
        description=(
            "High-level sector — drives smart defaults for the VC exit multiple "
            "and the regional comparable set (SaaS=6x, Marketplace=4x, Fintech=8x…)."
        ),
    )
    lifecycle_stage_triage: Optional[LifecycleStageTriage] = Field(
        None,
        description=(
            "Company-stage intelligence beside business type: tags, lifecycle stage, "
            "confidence, reasons, missing evidence, and signal provenance."
        ),
    )

    # --- Berkus / qualitative milestones (0-100 sliders) ---
    sound_idea: int = Field(50, ge=0, le=100, description="Sound idea / market need")
    prototype_status: int = Field(0, ge=0, le=100, description="Working prototype maturity")
    management_strength: int = Field(50, ge=0, le=100, description="Quality of the management team")
    strategic_relationships: int = Field(
        0, ge=0, le=100, description="Strategic partnerships / channels"
    )
    product_rollout: int = Field(0, ge=0, le=100, description="Product launch / first sales")

    # --- Scorecard inputs (0-100 sliders) ---
    opportunity_size: int = Field(50, ge=0, le=100, description="Size of the opportunity / TAM")
    competitive_environment: int = Field(50, ge=0, le=100, description="Competitive moat strength")
    sales_marketing_channels: int = Field(
        50, ge=0, le=100, description="Sales / marketing channel strength"
    )
    need_for_additional_funding: int = Field(
        50,
        ge=0,
        le=100,
        description="Funding self-sufficiency (higher = needs less additional capital)",
    )
    other_factors: int = Field(50, ge=0, le=100, description="Other positive factors")

    # --- Forward-looking traction ---
    mrr: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Monthly Recurring Revenue (EUR)"
    )
    arr: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Annual Recurring Revenue (EUR)"
    )
    mrr_growth_rate_pct: Optional[Decimal] = Field(
        None, description="Month-over-month MRR growth rate (%)"
    )
    monthly_churn_pct: Optional[Decimal] = Field(
        None, ge=Decimal("0"), le=Decimal("100"), description="Monthly logo or revenue churn (%)"
    )
    cac: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Customer Acquisition Cost (EUR)"
    )
    ltv: Optional[Decimal] = Field(None, ge=Decimal("0"), description="Lifetime Value (EUR)")
    burn_rate_monthly: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Monthly net burn (EUR)"
    )
    runway_months: Optional[Decimal] = Field(
        None, ge=Decimal("0"), description="Cash runway in months"
    )
    team_size: Optional[int] = Field(None, ge=0, le=10000, description="Headcount")
    # Engagement signal — interpretation is sector-dependent (MAU for
    # SaaS, registered/active accounts for marketplaces, DAU for
    # consumer).  Feeds the defensibility traction_signal only; not a
    # valuation-leg input.  Lets a marketplace founder with €1k ARR but
    # 500 active sellers earn more traction credit than a SaaS founder
    # with €1k ARR and 5 users — same revenue, very different real
    # signal.
    active_users: Optional[int] = Field(
        None,
        ge=0,
        le=100_000_000,
        description="Active users (MAU/MAA/DAU depending on sector)",
    )

    # --- VC Method inputs ---
    year5_revenue_projection: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Founder's projected revenue in Year 5 (EUR)",
    )
    exit_revenue_multiple: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Comparable exit EV/Revenue multiple at Year 5",
    )
    target_roi_x: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="VC required cash-on-cash return multiple (e.g. 10x-30x)",
    )
    dilution_assumption_pct: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("99"),
        description="Expected total founder dilution before exit (%)",
    )
    investment_amount_sought: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description=(
            "Funding amount the founder is currently raising (EUR).  "
            "Anchors the consortium-spec VC formula: "
            "pre_money = (Y5 revenue × exit multiple / target ROI) − investment_sought, "
            "and powers the 'if you raise €X you dilute Y%' cap-table simulator on the report."
        ),
    )

    # --- Cap table summary ---
    cap_table: CapTableSummary = Field(
        default_factory=CapTableSummary, description="Cap-table summary"
    )
    round_scenario: Optional[RoundScenario] = Field(
        None,
        description=(
            "Optional active/draft fundraising round scenario. This is market-implied "
            "evidence for graph overlays and dilution, not the objective valuation dot."
        ),
    )
    startup_benchmarks: List[StartupBenchmarkInput] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Optional local-average and comparable-round benchmark observations. "
            "Local averages can calibrate the Scorecard anchor; company-specific "
            "round/cap evidence is surfaced as market context and never overwrites "
            "the objective valuation dot."
        ),
    )

    # --- Founder pedigree (multiplicative overlay on the blend) ---
    #
    # See :mod:`.founder_pedigree` for the calibration. Defaults to all-false
    # so a payload that pre-dates this field reads as multiplier 1.0 (no
    # overlay) — backwards-compatible with every existing Studio v2 payload.
    founder_pedigree: FounderPedigreeInputs = Field(
        default_factory=FounderPedigreeInputs,
        description=(
            "Founder-team qualifications driving the pedigree multiplier "
            "(applied on top of the Berkus + Scorecard + VC + SaaS Forward blend)."
        ),
    )

    # --- Inception lens (opt-in overlay that fixes the three pre-seed gaps) ---
    #
    # Default ``milestones_driven`` is a no-op — every existing payload
    # behaves identically.  Founders who self-identify as momentum-driven
    # or as an inception bet opt into a multiplier + band-widening overlay
    # applied AFTER pedigree.  See :class:`InceptionLens` for calibration
    # rationale and :mod:`.synthesis` for the math.
    inception_lens: InceptionLens = Field(
        "milestones_driven",
        description=(
            "Opt-in lens that acknowledges three pre-seed realities the milestone-"
            "track methods miss: (1) moats don't exist yet, (2) TAM is unknowable, "
            "(3) edge founders cost more.  See module docstring."
        ),
    )

    # --- Studio v2 metadata (wizard signals; engine ignores today) ---
    #
    # Loose-typed bag mirroring `startupInputsSchema.studio_v2` on the
    # Titan side.  The Studio v3 Claude scorer will read these to ground
    # narrative output and cross-check evidence vs the milestone score.
    # Today the engine ignores the field — we accept it solely so the
    # Pydantic validator does not 422 on a Studio-driven payload.
    studio_v2: Optional[Dict[str, object]] = Field(
        default=None,
        description=(
            "Studio v2 wizard metadata (description, evidence_notes, tam_sam_som). "
            "Currently informational only — reserved for the v3 Claude scorer."
        ),
    )

    # `extra="ignore"` keeps the engine robust against any future Studio
    # signal landing in the payload before this schema is bumped.
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _coerce_arr_from_mrr(self) -> "StartupInputs":
        """If the founder gave us MRR but not ARR, derive ARR (and vice-versa)."""
        if self.arr is None and self.mrr is not None:
            object.__setattr__(self, "arr", self.mrr * Decimal("12"))
        if self.mrr is None and self.arr is not None:
            object.__setattr__(self, "mrr", self.arr / Decimal("12"))
        return self
