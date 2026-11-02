"""Post-template integrity checks for publishable valuation memoranda."""

from __future__ import annotations

from bs4 import BeautifulSoup

from src.services.reports.stateless_valuation_run import canonical_hash


class SealedReportHtmlAuditError(ValueError):
    def __init__(self, code: str, message: str, diagnostics: object | None = None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics


_REQUIRED_ECONOMIC_FIELD_IDS = {
    "conclusion.enterprise_value.mid",
    "conclusion.equity_value.low",
    "conclusion.equity_value.mid",
    "conclusion.equity_value.high",
    "bridge.equity_value",
}


def audit_sealed_report_html(
    html: str,
    *,
    snapshot_sha256: str,
    valuation_run_hash: str,
    display_model_hash: str,
    locale: str,
    assurance_level: str,
) -> dict[str, object]:
    """Verify identity, locale and asset isolation after Jinja has rendered."""

    soup = BeautifulSoup(html, "lxml")
    document = soup.find("html")
    root = soup.select_one("div.valuation-report[data-report-contract]")
    expected = {
        "data-report-contract": "ma_valuation_memorandum.v2",
        "data-render-snapshot-sha256": snapshot_sha256,
        "data-valuation-run-sha256": valuation_run_hash,
        "data-display-model-sha256": display_model_hash,
        "data-report-locale": locale,
        "data-report-assurance": assurance_level,
    }
    mismatches: dict[str, object] = {}
    if document is None or document.get("lang") != locale:
        mismatches["html.lang"] = None if document is None else document.get("lang")
    if root is None:
        mismatches["root"] = "missing"
    else:
        for key, value in expected.items():
            if root.get(key) != value:
                mismatches[key] = root.get(key)
    if mismatches:
        raise SealedReportHtmlAuditError(
            "SEALED_HTML_IDENTITY_MISMATCH",
            "Rendered memorandum identity does not match its sealed inputs.",
            mismatches,
        )

    prohibited_elements = [
        tag.name for tag in soup.select("script, iframe, object, embed")
    ]
    remote_assets: list[str] = []
    for tag in soup.select("img[src], link[href]"):
        locator = str(tag.get("src") or tag.get("href") or "").strip()
        if locator.startswith(("http://", "https://", "//")):
            remote_assets.append(locator)
        if (
            tag.name == "img"
            and locator
            and not locator.startswith(
                (
                    "data:image/png;base64,",
                    "data:image/jpeg;base64,",
                    "data:image/webp;base64,",
                )
            )
        ):
            remote_assets.append(locator)
    if prohibited_elements or remote_assets:
        raise SealedReportHtmlAuditError(
            "SEALED_HTML_ACTIVE_CONTENT_PROHIBITED",
            "Publishable memorandum HTML contains active or mutable external content.",
            {
                "elements": sorted(set(prohibited_elements)),
                "remote_assets": sorted(set(remote_assets)),
            },
        )

    unresolved_tokens = [token for token in ("{{", "{%", "{#") if token in html]
    if unresolved_tokens:
        raise SealedReportHtmlAuditError(
            "SEALED_HTML_TEMPLATE_TOKEN_LEAK",
            "Publishable memorandum HTML contains unresolved template tokens.",
            {"tokens": unresolved_tokens},
        )

    field_ids = sorted(
        {
            str(tag.get("data-sealed-field-id"))
            for tag in soup.select("[data-sealed-field-id]")
            if tag.get("data-sealed-field-id")
        }
    )
    missing_field_ids = sorted(_REQUIRED_ECONOMIC_FIELD_IDS.difference(field_ids))
    method_field_ids = [field_id for field_id in field_ids if field_id.startswith("method.")]
    if missing_field_ids or not method_field_ids:
        raise SealedReportHtmlAuditError(
            "SEALED_HTML_FIELD_COVERAGE_INCOMPLETE",
            "Rendered memorandum does not reference every required sealed economic field.",
            {
                "missing": missing_field_ids,
                "method_field_count": len(method_field_ids),
            },
        )
    audit_payload: dict[str, object] = {
        "schema_version": "sealed_report_html_audit.v1",
        "snapshot_sha256": snapshot_sha256,
        "valuation_run_hash": valuation_run_hash,
        "display_model_hash": display_model_hash,
        "locale": locale,
        "assurance_level": assurance_level,
        "field_ids": field_ids,
        "remote_asset_count": 0,
        "active_content_count": 0,
    }
    return {
        **audit_payload,
        "audit_sha256": canonical_hash(audit_payload),
    }
