"""OpenAPI schema configuration for the ValuationIQ API."""

from typing import Any, Dict, cast

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


OPENAPI_DESCRIPTION = """
ValuationIQ is the stateless valuation and report engine in the Brain & Muscle architecture.
Titan owns conversational orchestration, sessions, AI guidance, and persistent workflow state.

## Features

* **Stateless Calculations** - Deterministic valuation requests from Titan-owned input
* **Business Type Analysis** - Methodology selection and business-type intelligence
* **Valuation Engine** - DCF, multiples, and synthesized valuations
* **Report Generation** - HTML/PDF report rendering and buyer-ready packages
* **Registry Support** - Lightweight company registry integration where enabled

## API Endpoints

* `/api/v2/stateless/*` - Stateless calculation and report API
* `/api/v1/valuation/*` - Valuation calculations and results
* `/api/v1/reports/*` - Report generation
* `/api/v1/business-type/*` - Business type analysis
* `/api/v1/registry/*` - Registry lookup compatibility
"""


def configure_openapi(app: FastAPI) -> None:
    """Install the custom OpenAPI schema builder."""

    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return cast(Dict[str, Any], app.openapi_schema)

        openapi_schema = get_openapi(
            title="Upswitch Valuation Engine API",
            version="1.0.0",
            description=OPENAPI_DESCRIPTION,
            routes=app.routes,
        )

        openapi_schema["tags"] = [
            {"name": "stateless", "description": "Stateless valuation/report endpoints"},
            {"name": "valuation", "description": "Valuation calculations and results"},
            {"name": "reports", "description": "Report generation endpoints"},
            {
                "name": "business-type-analysis",
                "description": "Business type analysis and methodology selection",
            },
            {"name": "registry", "description": "Registry lookup compatibility"},
        ]

        app.openapi_schema = openapi_schema
        return cast(Dict[str, Any], app.openapi_schema)

    app.openapi = custom_openapi
