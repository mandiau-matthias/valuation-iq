"""Bounded campaign-page execution with a hash-chain resume contract."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import (
    CurveCompanyInputV1,
    MultipleContractV9,
    PublicCurveCampaignPlanV1,
    SHA256_PATTERN,
)
from .runner import PublicCurveBlockedV1, PublicCurveResultV1, run_public_curve


class CampaignPageResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "CampaignPageResultV1"
    campaign_request_id: str
    page_number: int = Field(ge=1)
    first_job_index: int = Field(ge=0)
    last_job_index: int = Field(ge=0)
    previous_page_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    result_sha256s: tuple[str, ...]
    blocked_fingerprints: tuple[str, ...]
    page_sha256: str = Field(pattern=SHA256_PATTERN)
    results: tuple[PublicCurveResultV1 | PublicCurveBlockedV1, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> "CampaignPageResultV1":
        if self.last_job_index < self.first_job_index:
            raise ValueError("last_job_index must be on or after first_job_index")
        if self.last_job_index - self.first_job_index + 1 != len(self.results):
            raise ValueError("campaign page index range must match its result count")
        return self


def _canonical_json(value: object) -> bytes:
    def default(item: object) -> object:
        if isinstance(item, Decimal):
            return format(item, "f")
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError(f"unsupported JSON value: {type(item).__name__}")

    return json.dumps(
        value,
        default=default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _page_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def execute_campaign_page(
    *,
    plan: PublicCurveCampaignPlanV1,
    page_number: int,
    companies_by_key: Mapping[str, CurveCompanyInputV1],
    contracts_by_id: Mapping[str, MultipleContractV9],
    previous_page_sha256: str | None = None,
) -> CampaignPageResultV1:
    """Execute at most 250 durable jobs from an immutable <=10K plan.

    Callers persist the returned page atomically and pass its hash into the next
    page.  Missing inputs are hard failures, preserving retryability rather
    than silently producing a partial page.
    """
    if page_number < 1:
        raise ValueError("page_number starts at 1")
    page_size = plan.durable_results_per_page
    first = (page_number - 1) * page_size
    jobs = plan.jobs[first : first + page_size]
    if not jobs:
        raise ValueError("campaign page falls outside the immutable job plan")

    results: list[PublicCurveResultV1 | PublicCurveBlockedV1] = []
    for job in jobs:
        company = companies_by_key.get(job.company_key)
        if company is None:
            raise KeyError(f"missing immutable company input: {job.company_key}")
        contracts: list[MultipleContractV9] = []
        for contract_id in job.contract_ids:
            contract = contracts_by_id.get(contract_id)
            if contract is None:
                raise KeyError(f"missing frozen contract: {contract_id}")
            if contract.multiple_manifest_sha256 != plan.snapshot.multiple_manifest_sha256:
                raise ValueError(f"contract {contract_id} does not bind the campaign manifest")
            contracts.append(contract)
        results.append(
            run_public_curve(
                campaign_request_id=plan.campaign_request_id,
                company=company,
                contracts=tuple(contracts),
                valuation_as_of=plan.created_at.date(),
                model_version=plan.model_version,
            )
        )

    result_sha256s = tuple(
        item.result_sha256 for item in results if isinstance(item, PublicCurveResultV1)
    )
    blocked_fingerprints = tuple(
        item.input_fingerprint for item in results if isinstance(item, PublicCurveBlockedV1)
    )
    hash_payload = {
        "campaign_request_id": plan.campaign_request_id,
        "page_number": page_number,
        "first_job_index": first,
        "last_job_index": first + len(jobs) - 1,
        "previous_page_sha256": previous_page_sha256,
        "result_sha256s": result_sha256s,
        "blocked_fingerprints": blocked_fingerprints,
    }
    return CampaignPageResultV1(
        campaign_request_id=plan.campaign_request_id,
        page_number=page_number,
        first_job_index=first,
        last_job_index=first + len(jobs) - 1,
        previous_page_sha256=previous_page_sha256,
        result_sha256s=result_sha256s,
        blocked_fingerprints=blocked_fingerprints,
        page_sha256=_page_hash(hash_payload),
        results=tuple(results),
    )


__all__ = ["CampaignPageResultV1", "execute_campaign_page"]
