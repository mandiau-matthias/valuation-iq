"""Generate a local indicative SME valuation using the original stateless engine."""
import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path

def offline(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise OSError("ValuationIQ local reports do not make network requests")


if __name__ == "__main__":
    sys.addaudithook(offline)
os.environ["STATELESS_MODE"] = "true"
os.environ.setdefault("VALUATION_HONEST_PRESENTATION_ENABLED", "true")
from src.api.routes.stateless_calculation_router import calculate
from src.api.routes.stateless_router import generate_report, validate
from src.api.schemas.stateless_api import CalculateRequest, GenerateReportRequest, ValidateRequest


async def run(input_file: Path, output: Path):
    payload = json.loads(input_file.read_text())
    request = CalculateRequest.model_validate(payload)
    validation = await validate(ValidateRequest.model_validate({
        key: value for key, value in payload.items() if key in ValidateRequest.model_fields
    }))
    if not validation.ready_for_calculation:
        raise ValueError(f"Inputs incomplete: {validation.model_dump_json()}")
    result = await calculate(request)
    report = await generate_report(GenerateReportRequest(
        valuation_result=result, company_name=request.company_name,
        country_code=request.country_code, industry=request.industry,
        founding_year=request.founding_year, language="en", include_pdf=True,
        selected_method=request.selected_method, reporting_year=request.current_year.year,
        current_year_data=request.current_year, historical_years_data=request.historical_years,
    ))
    pdf = base64.b64decode(report.pdf_base64 or "", validate=True)
    if not pdf.startswith(b"%PDF-"):
        raise ValueError(f"No PDF was produced: {report.generation_warnings}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "valuation.json").write_text(result.model_dump_json(indent=2) + "\n")
    (output / "report.pdf").write_bytes(pdf)
    print(f"Generated {output / 'report.pdf'} and {output / 'valuation.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", nargs="?", default="examples/company.json", type=Path)
    parser.add_argument("--out", default="output", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.case, args.out))
