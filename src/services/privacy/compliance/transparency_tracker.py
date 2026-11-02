"""
Transparency Tracker

Tracks calculation steps, market data, and validation results
for full auditability of the valuation process.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


class TransparencyTracker:
    """Tracks valuation calculation transparency data."""

    def __init__(self):
        self._steps: List[Dict[str, Any]] = []
        self._market_data: List[Dict[str, Any]] = []
        self._benchmarks: List[Dict[str, Any]] = []
        self._methodology_notes: Optional[str] = None
        self._validation_report: Optional[Dict[str, Any]] = None

    def track_calculation(
        self,
        step_name: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        formula: Optional[str] = None,
        sources: Optional[List[str]] = None,
    ) -> None:
        self._steps.append({
            "step_name": step_name,
            "inputs": inputs,
            "outputs": outputs,
            "formula": formula,
            "sources": sources or [],
            "timestamp": datetime.utcnow().isoformat(),
        })

    def add_calculation_step(
        self,
        description: str,
        formula: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        explanation: str = "",
    ) -> None:
        self._steps.append({
            "step_name": description,
            "formula": formula,
            "inputs": inputs,
            "outputs": outputs,
            "explanation": explanation,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def record_market_data(
        self,
        data_type: str,
        value: Any,
        source_type: str,
        **kwargs: Any,
    ) -> None:
        self._market_data.append({
            "data_type": data_type,
            "value": value,
            "source_type": source_type,
            **kwargs,
        })

    def record_industry_benchmark(
        self,
        benchmark_type: str,
        company_value: Any,
        benchmark_value: Any,
        **kwargs: Any,
    ) -> None:
        self._benchmarks.append({
            "benchmark_type": benchmark_type,
            "company_value": company_value,
            "benchmark_value": benchmark_value,
            **kwargs,
        })

    def set_methodology_notes(self, notes: str) -> None:
        self._methodology_notes = notes

    def set_validation_report(
        self,
        overall_score: Any,
        checks: Any,
        summary: Any,
    ) -> None:
        self._validation_report = {
            "overall_score": overall_score,
            "checks": checks,
            "summary": summary,
        }

    def get_transparency_data(self) -> Dict[str, Any]:
        return {
            "calculation_steps": self._steps,
            "market_data": self._market_data,
            "benchmarks": self._benchmarks,
            "methodology_notes": self._methodology_notes,
            "validation_report": self._validation_report,
        }
