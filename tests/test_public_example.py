"""Reference checks for the exact public example. Requires Poppler for PDF inspection."""
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError
from src.api.schemas.stateless_common import YearDataStateless

ROOT = Path(__file__).resolve().parents[1]


class PublicExample(unittest.TestCase):
    def test_zero_earnings_are_not_missing(self):
        year = {"year": 2025, "revenue": "1000000", "ebitda": "0"}
        self.assertEqual(YearDataStateless.model_validate(year).ebitda, Decimal("0"))
        del year["ebitda"]
        with self.assertRaises(ValidationError):
            YearDataStateless.model_validate(year)

    def test_sample_pdf_agrees_with_machine_readable_bridge(self):
        result = json.loads((ROOT / "examples/valuation.json").read_text())
        text = subprocess.check_output(["pdftotext", "-layout", ROOT / "examples/report.pdf", "-"], text=True)
        for key in ("enterprise_value_mid", "equity_value_mid"):
            self.assertIn(f"€{Decimal(result[key]):,.0f}", text)
        self.assertEqual(Decimal(result["equity_value_mid"]), Decimal("821325"))
        self.assertEqual(Decimal(result["enterprise_value_mid"]), Decimal("896325"))

    def test_zero_reported_earnings_stay_distinct_from_weighted_earnings_in_the_report(self):
        case = json.loads((ROOT / "examples/company.json").read_text())
        case["current_year"]["ebitda"] = "0"
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            input_file = out / "zero.json"
            input_file.write_text(json.dumps(case))
            subprocess.run([sys.executable, ROOT / "value.py", input_file, "--out", out],
                           check=True, stdout=subprocess.DEVNULL)
            result = json.loads((out / "valuation.json").read_text())
            text = subprocess.check_output(["pdftotext", "-layout", out / "report.pdf", "-"], text=True)
        metrics = result["valuation_run"]["financial_metrics"]
        self.assertEqual(Decimal(metrics["reported_ebitda"]), Decimal(0))
        self.assertEqual(Decimal(metrics["valuation_basis_ebitda"]), Decimal(85000))
        self.assertRegex(text, r"Latest reported EBITDA\s+€0(?:\.00)?\b")
        self.assertRegex(text, r"Weighted EBITDA before adjustments\s+€85,000(?:\.00)?\b")
