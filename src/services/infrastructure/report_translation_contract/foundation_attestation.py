"""Attestation foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationAttestationFields:
    # =========================================================================
    # ATTESTATION PAGE (Enterprise / accountant-branded only)
    # =========================================================================
    # Rendered when ``accountant_firm_name`` is set on the report context.
    # Provides a signature-ready block that the preparing accountant + the
    # client co-sign. Gives the report the "ondertekende verklaring" status
    # an M&A practitioner needs to put their name on.
    attestation_title: str
    attestation_intro: str
    attestation_intro_asset: str
    attestation_intro_yield: str
    attestation_caveat: str
    attestation_preparer_role: str
    attestation_client_role: str
    attestation_signature_label: str
    attestation_date_label: str

