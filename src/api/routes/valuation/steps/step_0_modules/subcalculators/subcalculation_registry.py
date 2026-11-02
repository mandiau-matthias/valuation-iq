from typing import List, Optional

from .base_subcalculator import Step0Subcalculator
from .saas_subcalculator import SaaSSubcalculator


class Step0SubcalculationRegistry:
    def __init__(self, calculators: Optional[List[Step0Subcalculator]] = None):
        self._calculators = calculators or [SaaSSubcalculator()]

    def get_applicable(self, request) -> List[Step0Subcalculator]:
        return [calculator for calculator in self._calculators if calculator.applies(request)]
