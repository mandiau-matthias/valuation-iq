"""
Step 6 Liquidity Discount Modules

Specialized modules for Step 6 liquidity discount calculation.
"""

# This __init__.py makes step_6_liquidity_discount a package
# The main Step6LiquidityDiscount class is in step_6_liquidity_discount.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step6LiquidityDiscount from the parent file
def __getattr__(name: str) -> object:
    if name == "Step6LiquidityDiscount":
        return load_step_class(
            __file__, "step_6_liquidity_discount.py", "Step6LiquidityDiscount", "_step_file"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
