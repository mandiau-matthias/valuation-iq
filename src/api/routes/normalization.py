from fastapi import APIRouter, Depends

from src.api.schemas.normalization_scan import (
    LeaseScanRequest,
    LeaseScanResponse,
    LeaseYearResult,
    OwnerBenefitFindingItem,
    OwnerBenefitScanRequest,
    OwnerBenefitScanResponse,
    OwnerBenefitYearResult,
    RelatedPartyScanRequest,
    RelatedPartyScanResponse,
    RelatedPartyYearResult,
    SDEFlagItem,
    SDEFlagScanRequest,
    SDEFlagScanResponse,
)
from src.domain.lease_normalizer import LeaseNormalizer
from src.domain.owner_benefit_detector import OwnerBenefitDetector
from src.domain.related_party_detector import RelatedPartyDetector
from src.domain.sde_flag_scanner import scan_trial_balance_for_sde_flags
from src.middleware.auth import require_service_auth

router = APIRouter(
    prefix="/normalization",
    tags=["normalization"],
    dependencies=[Depends(require_service_auth)],
)


@router.post("/scan-sde-flags", response_model=SDEFlagScanResponse)
async def scan_sde_flags(request: SDEFlagScanRequest) -> SDEFlagScanResponse:
    years: dict[str, list[SDEFlagItem]] = {}
    total_flags = 0

    for year_data in request.years:
        flags = scan_trial_balance_for_sde_flags(
            [entry.model_dump() for entry in year_data.entries],
            revenue=year_data.revenue,
            industry=request.industry,
            sector_benchmarks=request.sector_benchmarks,
            year=year_data.year,
        )
        years[str(year_data.year)] = [SDEFlagItem(**flag) for flag in flags]
        total_flags += len(flags)

    return SDEFlagScanResponse(total_flags=total_flags, years=years)


@router.post("/scan-related-party", response_model=RelatedPartyScanResponse)
async def scan_related_party(request: RelatedPartyScanRequest) -> RelatedPartyScanResponse:
    """
    Scan trial balance entries for related-party transactions and propose
    EBITDA normalizations. Returns per-year findings with confidence scores,
    proposed add-back amounts, and suggested advisor questions.
    """
    detector = RelatedPartyDetector()
    year_results: dict[str, RelatedPartyYearResult] = {}
    total_findings = 0
    total_adj = 0.0

    for year_data in request.years:
        result = detector.scan(
            [entry.model_dump() for entry in year_data.entries],
            revenue=year_data.revenue,
            industry=request.industry,
            known_owner_entities=request.known_owner_entities,
            year=year_data.year,
        )
        year_results[str(year_data.year)] = RelatedPartyYearResult(**result.to_dict())
        total_findings += len(result.findings)
        total_adj += result.total_proposed_ebitda_adjustment

    return RelatedPartyScanResponse(
        total_findings=total_findings,
        total_proposed_ebitda_adjustment=round(total_adj, 2),
        years=year_results,
    )


@router.post("/scan-lease-ifrs16", response_model=LeaseScanResponse)
async def scan_lease_ifrs16(request: LeaseScanRequest) -> LeaseScanResponse:
    """
    Identify operating lease lines in the trial balance and compute the
    IFRS 16 EBITDA add-back for each year. Flags GAAP/IFRS divergence
    and materiality when the add-back exceeds 5% of reported EBITDA.
    """
    normalizer = LeaseNormalizer()
    year_results: dict[str, LeaseYearResult] = {}
    total_lease = 0.0
    total_addback = 0.0

    for year_data in request.years:
        result = normalizer.normalize(
            [entry.model_dump() for entry in year_data.entries],
            revenue=year_data.revenue,
            reported_ebitda=year_data.reported_ebitda,
            industry=request.industry,
            country=request.country,
            year=year_data.year,
        )
        year_results[str(year_data.year)] = LeaseYearResult(**result.to_dict())
        total_lease += result.total_operating_lease_expense
        total_addback += result.total_ifrs16_ebitda_addback

    return LeaseScanResponse(
        total_lease_expense=round(total_lease, 2),
        total_ifrs16_ebitda_addback=round(total_addback, 2),
        years=year_results,
    )


@router.post("/scan-owner-benefits", response_model=OwnerBenefitScanResponse)
async def scan_owner_benefits(request: OwnerBenefitScanRequest) -> OwnerBenefitScanResponse:
    """
    Scan trial balance entries for owner pension contributions and personal
    benefit items (IPT, VAPZ, hospitalisatie, company car, home office,
    memberships). Proposes EBITDA add-backs for M&A normalization.

    All findings are propose-only — advisor confirmation required before
    inclusion in the normalization schedule.
    """
    detector = OwnerBenefitDetector()
    year_results: dict[str, OwnerBenefitYearResult] = {}
    total_findings = 0
    total_adj = 0.0
    any_vapz_breach = False

    for year_data in request.years:
        result = detector.scan(
            [entry.model_dump() for entry in year_data.entries],
            year=year_data.year,
            owner_count=request.owner_count,
            country=request.country,
        )
        yr = OwnerBenefitYearResult(
            year=result.year,
            findings=[OwnerBenefitFindingItem(**f.to_dict()) for f in result.findings],
            total_proposed_ebitda_adjustment=result.total_proposed_ebitda_adjustment,
            high_confidence_count=result.high_confidence_count,
            vapz_cap_breach=result.vapz_cap_breach,
            explanation=result.explanation,
        )
        year_results[str(year_data.year)] = yr
        total_findings += len(result.findings)
        total_adj += result.total_proposed_ebitda_adjustment
        any_vapz_breach = any_vapz_breach or result.vapz_cap_breach

    return OwnerBenefitScanResponse(
        total_findings=total_findings,
        total_proposed_ebitda_adjustment=round(total_adj, 2),
        vapz_cap_breach=any_vapz_breach,
        years=year_results,
    )
