"""English-only cascade tier label overlays."""

from __future__ import annotations

from typing import Dict


CASCADE_TIER_LABELS_EN: Dict[str, str] = {
    "estate_costs": "Estate costs (trustee fees + post-petition contracts)",
    "secured": "Secured creditors (mortgage + pledge + retention liens)",
    "super_preferent_employees": "Super-preferent payroll (RSZ + wage claims)",
    "preferent_tax": "Preferent tax (VAT + withholding) — general fiscus privilege",
    "preferent_other": "Other preferent claims",
    "unsecured": "Unsecured (concurrent) creditors",
    "subordinated": "Subordinated creditors + shareholder loans",
}
