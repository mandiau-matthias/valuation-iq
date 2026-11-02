from src.utils.exceptions import MultiplesCalculationError

"""
Business Type Multiples Adapter

Adapts business type benchmark data to the valuation engine's expected format.
Fetches multiples from PostgreSQL business_type_benchmarks table.

@author UpSwitch CTO Team
@version 1.0.0
@date January 27, 2025
"""

from typing import Optional, Dict, Any
from decimal import Decimal

from src.utils.country_code import normalize_iso3166_alpha2
from src.utils.logging import get_logger
from src.domain.models import IndustryBenchmarks
from src.database.business_types_repository import get_business_types_repository, BusinessTypeBenchmark
from src.utils.decimal_helpers import to_decimal, from_decimal, optional_decimal

logger = get_logger(__name__)


# ============================================================================
# MODEL COERCION
# ============================================================================
#
# `IndustryBenchmarks` (src/domain/models.py) is the canonical domain model.
# It takes fraction-based growth/margin, an enum confidence, and bounded
# multiples. The benchmark rows arriving from Athena/Delphi are percent-based
# and unbounded, so every value crosses this boundary through one of the
# helpers below. Anything that cannot be represented honestly is dropped to
# None and reported, never clamped into a plausible-looking number.

# Model bounds, mirrored from `IndustryBenchmarks`.
_MULTIPLE_BOUNDS = {
    "median_ev_ebitda": Decimal("100.0"),
    "median_ev_revenue": Decimal("50.0"),
    "median_pe": Decimal("200.0"),
}


def _as_ratio(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Normalize a percent-or-fraction benchmark into a fraction.

    Benchmark publishers are inconsistent: `ebitda_margin` arrives as either
    12.0 or 0.12 for the same 12%. Values with magnitude above 1 are read as
    percent. A true 100%+ margin does not occur in this corpus, so the
    ambiguity resolves safely in favour of percent.
    """
    parsed = optional_decimal(value)
    if parsed is None:
        return default
    return parsed / Decimal("100") if abs(parsed) > Decimal("1") else parsed


def _bounded_multiple(value: Any, field: str, business_type_id: str) -> Optional[Decimal]:
    """Accept a multiple only if the domain model can represent it."""
    parsed = optional_decimal(value)
    if parsed is None:
        return None
    if parsed < 0 or parsed > _MULTIPLE_BOUNDS[field]:
        logger.warning(
            "Benchmark multiple outside the domain range; dropping rather than clamping",
            extra={"business_type_id": business_type_id, "field": field, "value": str(parsed)},
        )
        return None
    return parsed


def _confidence_level(score: Optional[Decimal]) -> str:
    """Map the 0..1 data-quality score onto the model's confidence enum."""
    if score is None:
        return "low"
    if score >= Decimal("0.7"):
        return "high"
    if score >= Decimal("0.4"):
        return "medium"
    return "low"


# ============================================================================
# ADAPTER
# ============================================================================

class BusinessTypeMultiplesAdapter:
    """
    Adapter to convert business type benchmarks to IndustryBenchmarks format.

    This bridges the new business type intelligence system with the existing
    valuation engine, allowing dynamic multiples from the database.
    """

    def __init__(self):
        """Initialize the adapter"""
        self.logger = get_logger(__name__)

    _safe_decimal = staticmethod(optional_decimal)

    def get_industry_benchmarks_for_business_type(
        self,
        business_type_id: str,
        country_code: str = 'BE',
        fallback_to_defaults: bool = True
    ) -> Optional[IndustryBenchmarks]:
        """
        Get industry benchmarks for a business type from database.

        This method:
        1. Fetches benchmarks from business_type_benchmarks table
        2. Converts to IndustryBenchmarks format expected by valuation engine
        3. Falls back to default values if no data found (optional)

        Args:
            business_type_id: Business type ID (e.g., 'bakery', 'saas')
            country_code: ISO country code (default: 'BE')
            fallback_to_defaults: If True, return defaults if no data found

        Returns:
            IndustryBenchmarks object or None
        """
        try:
            cc = normalize_iso3166_alpha2(country_code)
            self.logger.info(f"Fetching benchmarks for business type: {business_type_id}")

            # Fetch benchmarks from database
            with get_business_types_repository() as repo:
                benchmarks = repo.get_benchmarks(
                    business_type_id=business_type_id,
                    country_code=cc,
                )

                if not benchmarks:
                    self.logger.warning(f"No benchmarks found for {business_type_id}")
                    if fallback_to_defaults:
                        return self._get_default_benchmarks(business_type_id, cc)
                    return None

                # Convert to IndustryBenchmarks format
                industry_benchmarks = self._convert_to_industry_benchmarks(
                    benchmarks=benchmarks,
                    business_type_id=business_type_id,
                    country_code=cc,
                )

                self.logger.info(
                    f"Successfully loaded benchmarks for {business_type_id}",
                    ev_ebitda=industry_benchmarks.median_ev_ebitda,
                    ev_revenue=industry_benchmarks.median_ev_revenue
                )

                return industry_benchmarks

        except MultiplesCalculationError as e:
            self.logger.error(f"Error fetching benchmarks for {business_type_id}: {e}")
            if fallback_to_defaults:
                return self._get_default_benchmarks(
                    business_type_id, normalize_iso3166_alpha2(country_code)
                )
            return None

    def _convert_to_industry_benchmarks(
        self,
        benchmarks: list,
        business_type_id: str,
        country_code: str
    ) -> IndustryBenchmarks:
        """
        Convert business type benchmarks to IndustryBenchmarks format.

        Args:
            benchmarks: List of BusinessTypeBenchmark objects
            business_type_id: Business type ID
            country_code: Country code

        Returns:
            IndustryBenchmarks object
        """
        # Create a dictionary for easy lookup
        benchmark_dict = {b.metric_name: b for b in benchmarks}

        # Extract valuation multiples
        ev_ebitda_benchmark = benchmark_dict.get('ev_ebitda_multiple')
        ev_revenue_benchmark = benchmark_dict.get('ev_revenue_multiple')
        pe_benchmark = benchmark_dict.get('pe_multiple')

        # Extract financial metrics
        ebitda_margin_benchmark = benchmark_dict.get('ebitda_margin')
        net_margin_benchmark = benchmark_dict.get('net_margin')
        revenue_growth_benchmark = benchmark_dict.get('revenue_growth')

        # Extract operational metrics
        revenue_per_employee_benchmark = benchmark_dict.get('revenue_per_employee')

        # Percentiles, sample size, source and vintage are NOT model fields.
        # They travel in the provenance record (`_build_provenance`) so the
        # report can state where a multiple came from; stuffing them in here is
        # what previously made every construction raise ValidationError.
        industry_benchmarks = IndustryBenchmarks(
            industry=business_type_id,
            region=country_code,
            expected_growth_rate=_as_ratio(
                revenue_growth_benchmark.median if revenue_growth_benchmark else None,
                default=Decimal("0.02"),
            ),
            avg_ebitda_margin=_as_ratio(
                ebitda_margin_benchmark.median if ebitda_margin_benchmark else None
            ),
            median_ev_ebitda=_bounded_multiple(
                ev_ebitda_benchmark.median if ev_ebitda_benchmark else None,
                "median_ev_ebitda",
                business_type_id,
            ),
            median_ev_revenue=_bounded_multiple(
                ev_revenue_benchmark.median if ev_revenue_benchmark else None,
                "median_ev_revenue",
                business_type_id,
            ),
            median_pe=_bounded_multiple(
                pe_benchmark.median if pe_benchmark else None,
                "median_pe",
                business_type_id,
            ),
            data_quality=_confidence_level(self._calculate_data_quality(benchmarks)),
        )

        return industry_benchmarks

    def get_industry_benchmarks_with_provenance(
        self,
        business_type_id: str,
        country_code: str = 'BE',
        fallback_to_defaults: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Return benchmarks PLUS the Delphi provenance dict.

        Audit closure 2026-05-02: the legacy
        `get_industry_benchmarks_for_business_type` returns IndustryBenchmarks
        only — defensibility metadata stops at the Athena public API.
        Consumers (report renderers, cover-confidence chip) need the
        triage layer, country basis, sample size, freshness, source
        alignment, and any required attribution to render truthfully.

        Returns:
            {"benchmarks": IndustryBenchmarks, "provenance": {...}}
            or None if no data and fallback disabled.
        """
        benchmarks = self.get_industry_benchmarks_for_business_type(
            business_type_id=business_type_id,
            country_code=country_code,
            fallback_to_defaults=fallback_to_defaults,
        )
        if benchmarks is None:
            return None
        try:
            cc = normalize_iso3166_alpha2(country_code)
            with get_business_types_repository() as repo:
                raw = repo.get_benchmarks(
                    business_type_id=business_type_id,
                    country_code=cc,
                )
        except MultiplesCalculationError as e:
            self.logger.warning(
                f"Provenance fetch failed; returning benchmarks without metadata: {e}"
            )
            return {"benchmarks": benchmarks, "provenance": {}}

        provenance = self._build_provenance(raw, business_type_id, cc)
        return {"benchmarks": benchmarks, "provenance": provenance}

    @staticmethod
    def _build_provenance(
        benchmarks: list,
        business_type_id: str,
        country_code: str,
    ) -> Dict[str, Any]:
        """Aggregate per-metric provenance into a single report-ready dict.

        Picks the most populated row's provenance (typically EV/EBITDA),
        falling back to whichever metric carries the metadata. Returns
        keys the report renderer can consume directly:
        - country_basis, selected_layer, confidence_band, source_alignment,
          freshness_band, last_observation_at, attribution_required
        - sample_size_max: largest sample size across metrics
        - layer_label: human string ("Layer 2 (Listed comps)") for the cover
        """
        layer_names = {
            1: "Country-official filings",
            2: "Listed comps",
            3: "Tier-1 proximity",
            4: "Tier-2 DACH/EU",
            5: "Broader sector local",
            6: "Macro anchor",
            7: "Semantic NACE fallback",
        }
        if not benchmarks:
            return {
                "business_type_id": business_type_id,
                "country_code": country_code,
                "country_basis": None,
                "selected_layer": None,
                "confidence_band": None,
                "source_alignment": None,
                "freshness_band": None,
                "last_observation_at": None,
                "attribution_required": None,
                "sample_size": 0,
                "sample_size_max": 0,
                "layer_label": None,
            }
        # Pick the most defensible row first — prefer one that carries any
        # provenance metadata, then EV/EBITDA, then whatever's present.
        ranked = sorted(
            benchmarks,
            key=lambda b: (
                0 if (b.selected_layer or b.country_basis) else 1,
                0 if b.metric_name == "ev_ebitda_multiple" else 1,
            ),
        )
        primary = ranked[0]
        sample_size_max = max((int(b.sample_size or 0) for b in benchmarks), default=0)
        layer = primary.selected_layer
        return {
            "business_type_id": business_type_id,
            "country_code": country_code,
            "country_basis": primary.country_basis,
            "selected_layer": layer,
            "confidence_band": primary.confidence_band,
            "source_alignment": primary.source_alignment,
            "freshness_band": primary.freshness_band,
            "last_observation_at": primary.last_observation_at,
            "attribution_required": primary.attribution_required,
            # `sample_size` belongs to the row that actually carries the quoted
            # layer/confidence. `sample_size_max` spans every metric, so citing
            # it next to the layer would overstate the evidence behind the
            # headline multiple.
            "sample_size": int(primary.sample_size or 0),
            "sample_size_max": sample_size_max,
            "layer_label": (
                f"Layer {layer} ({layer_names.get(layer, 'unknown')})"
                if layer
                else None
            ),
        }

    def _calculate_data_quality(self, benchmarks: list) -> Decimal:
        """
        Calculate data quality score based on number of benchmarks and sample sizes.

        Args:
            benchmarks: List of BusinessTypeBenchmark objects

        Returns:
            Quality score between Decimal('0.0') and Decimal('1.0')
        """
        if not benchmarks:
            return Decimal('0.0')

        # Base quality on number of benchmarks. Both terms stay Decimal: mixing a
        # float ratio with Decimal weights raises TypeError on every partially
        # covered business type, which is the common case.
        benchmark_coverage = min(
            Decimal(len(benchmarks)) / Decimal('6'), Decimal('1.0')
        )  # 6 = ideal number

        # Adjust for sample sizes
        avg_sample_size = Decimal(sum(int(b.sample_size or 0) for b in benchmarks)) / Decimal(
            len(benchmarks)
        )
        sample_quality = min(avg_sample_size / Decimal('100'), Decimal('1.0'))  # 100 = ideal sample

        # Combined score (70% coverage, 30% sample size)
        quality = (benchmark_coverage * Decimal('0.7')) + (sample_quality * Decimal('0.3'))

        return round(quality, 2)

    def _get_default_benchmarks(
        self, business_type_id: str, country_code: str = 'BE'
    ) -> IndustryBenchmarks:
        """
        Get default/fallback benchmarks when database data not available.

        These are conservative estimates based on general industry knowledge.
        They carry `low` confidence and no provenance on purpose: a defaulted
        multiple must never read as sourced evidence.

        Args:
            business_type_id: Business type ID
            country_code: Country the caller asked for, kept so a defaulted
                benchmark is not silently relabelled as Belgian

        Returns:
            IndustryBenchmarks with default values
        """
        self.logger.warning(f"Using default benchmarks for {business_type_id}")

        # Conservative defaults for SME businesses
        return IndustryBenchmarks(
            industry=business_type_id,
            region=country_code,
            expected_growth_rate=Decimal('0.05'),
            avg_ebitda_margin=Decimal('0.12'),
            median_ev_ebitda=Decimal('4.5'),
            median_ev_revenue=Decimal('0.6'),
            median_pe=Decimal('10.0'),
            data_quality="low",  # Defaults are never presented as sourced
        )

    def get_multiples_provenance(
        self,
        business_type_id: str,
        country_code: str = 'BE',
    ) -> Dict[str, Any]:
        """Return only the Delphi triage provenance for a business type.

        `get_multiples_dict` deliberately returns bare numbers for the hot
        path. This is its companion: the report needs to state which triage
        layer priced the multiple, over how many observations, and how stale
        it is. Returns an all-None provenance dict rather than raising, so a
        provenance miss can never suppress a usable multiple.
        """
        try:
            cc = normalize_iso3166_alpha2(country_code)
            with get_business_types_repository() as repo:
                raw = repo.get_benchmarks(business_type_id=business_type_id, country_code=cc)
            return self._build_provenance(raw, business_type_id, cc)
        except MultiplesCalculationError as e:
            self.logger.warning(
                f"Provenance lookup failed for {business_type_id}: {e}",
                extra={'business_type_id': business_type_id, 'country_code': country_code},
            )
            return self._build_provenance([], business_type_id, country_code)

    def get_multiples_dict(
        self,
        business_type_id: str,
        country_code: str = 'BE'
    ) -> Dict[str, Decimal]:
        """
        Get a simple dictionary of valuation multiples.

        Useful for quick lookups without full IndustryBenchmarks object.

        Args:
            business_type_id: Business type ID
            country_code: Country code

        Returns:
            Dict with multiple names and values
        """
        try:
            cc = normalize_iso3166_alpha2(country_code)
            self.logger.info(
                f"🔍 Fetching DB multiples for business_type_id: {business_type_id}",
                extra={"business_type_id": business_type_id, "country_code": cc},
            )

            with get_business_types_repository() as repo:
                multiples = repo.get_valuation_multiples(
                    business_type_id=business_type_id,
                    country_code=cc,
                )

                # Rename keys to match expected format
                result = {}
                if 'ev_ebitda_multiple' in multiples:
                    result['ev_ebitda'] = self._safe_decimal(multiples['ev_ebitda_multiple'])
                if 'ev_revenue_multiple' in multiples:
                    result['ev_revenue'] = self._safe_decimal(multiples['ev_revenue_multiple'])
                if 'pe_multiple' in multiples:
                    result['pe'] = self._safe_decimal(multiples['pe_multiple'])

                if result:
                    self.logger.info(
                        f"✅ DB multiples retrieved successfully",
                        extra={
                            'business_type_id': business_type_id,
                            'country_code': cc,
                            'multiples': result
                        }
                    )
                else:
                    self.logger.warning(
                        f"⚠️ DB returned empty multiples",
                        extra={'business_type_id': business_type_id, 'country_code': cc}
                    )

                return result

        except MultiplesCalculationError as e:
            self.logger.error(
                f"❌ Error fetching multiples dict: {e}",
                extra={
                    'business_type_id': business_type_id,
                    'country_code': normalize_iso3166_alpha2(country_code),
                    'error_type': type(e).__name__
                },
                exc_info=True
            )
            return {}


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def get_business_type_multiples_adapter() -> BusinessTypeMultiplesAdapter:
    """
    Factory function to get a BusinessTypeMultiplesAdapter instance.

    Returns:
        BusinessTypeMultiplesAdapter instance

    Usage:
        adapter = get_business_type_multiples_adapter()
        benchmarks = adapter.get_industry_benchmarks_for_business_type('bakery')

        # Use benchmarks in valuation engine
        multiples_engine = MarketMultiplesEngine(
            financial_data=financial_data,
            market_context=market_context,
            industry_benchmarks=benchmarks
        )
    """
    return BusinessTypeMultiplesAdapter()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Get benchmarks for bakery
    adapter = get_business_type_multiples_adapter()

    # Get full IndustryBenchmarks object
    benchmarks = adapter.get_industry_benchmarks_for_business_type('bakery')
    if benchmarks:
        print(f"Industry: {benchmarks.industry_name}")
        print(f"EV/EBITDA: {benchmarks.median_ev_ebitda}x")
        print(f"EV/Revenue: {benchmarks.median_ev_revenue}x")
        print(f"P/E: {benchmarks.median_pe}x")
        print(f"EBITDA Margin: {benchmarks.median_ebitda_margin}%")
        print(f"Companies Count: {benchmarks.companies_count}")
        print(f"Data Quality: {benchmarks.data_quality}")
        print(f"Data Source: {benchmarks.data_source}")

    # Get simple multiples dict
    multiples_dict = adapter.get_multiples_dict('bakery', 'BE')
    print(f"\nMultiples Dict: {multiples_dict}")

