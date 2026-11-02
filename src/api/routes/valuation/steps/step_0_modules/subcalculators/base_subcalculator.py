from typing import Any, Dict, Optional, Protocol


class Step0Subcalculator(Protocol):
    key: str

    def applies(self, request: Any) -> bool:
        ...

    def calculate(self, request: Any) -> Optional[Dict[str, Any]]:
        ...
