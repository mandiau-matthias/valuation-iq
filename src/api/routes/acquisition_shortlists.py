"""Service-authenticated, typed rendering only; Titan owns recipient access and publication."""

import asyncio
import base64
from fastapi import APIRouter, Depends
from src.middleware.auth import require_service_auth
from src.domain.acquisition_shortlist import AcquisitionShortlistRenderRequest
from src.services.reports.acquisition_shortlist_render import render_shortlist

router = APIRouter(
    prefix="/acquisition-shortlists",
    tags=["acquisition-shortlists"],
    dependencies=[Depends(require_service_auth)],
)


@router.post("/render")
async def render_acquisition_shortlist(body: AcquisitionShortlistRenderRequest):
    html, pdf = await asyncio.wait_for(
        asyncio.to_thread(render_shortlist, body.snapshot), timeout=75
    )
    return {"sha256": body.sha256, "html": html, "pdfBase64": base64.b64encode(pdf).decode()}
