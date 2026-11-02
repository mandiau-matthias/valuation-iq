"""Optional local reference inputs. Their provider retains its data rights."""
import json
import os
from decimal import Decimal
from pathlib import Path


def reference_table(name):
    directory = os.environ.get("VALUATIONIQ_REFERENCE_DIR")
    if not directory:
        return {}
    path = Path(directory) / (name + ".json")
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(), parse_float=Decimal)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value
