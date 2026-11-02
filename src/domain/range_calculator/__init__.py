from .multiples_dispersion_calculator import MultiplesDispersionCalculator

# Import ValuationRangeCalculator from the file (not package) to avoid circular import
import sys
import importlib.util
from pathlib import Path

# Get the parent directory
parent_dir = Path(__file__).parent.parent
range_calc_file = parent_dir / "range_calculator.py"

if range_calc_file.exists():
    spec = importlib.util.spec_from_file_location("range_calculator_module", range_calc_file)
    range_calc_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(range_calc_module)
    ValuationRangeCalculator = range_calc_module.ValuationRangeCalculator
else:
    # Fallback: try direct import
    from src.domain.range_calculator import ValuationRangeCalculator

__all__ = ["MultiplesDispersionCalculator", "ValuationRangeCalculator"]

