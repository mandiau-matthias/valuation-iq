from decimal import Decimal
from typing import Any

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal

_DEFAULT_BENCHMARKS: dict[str, dict[str, tuple[Decimal, Decimal]]] = {
    "technology": {
        "61": (Decimal("0.12"), Decimal("0.04")),
        "611": (Decimal("0.02"), Decimal("0.01")),
        "62": (Decimal("0.34"), Decimal("0.08")),
    },
    "manufacturing": {
        "61": (Decimal("0.09"), Decimal("0.03")),
        "611": (Decimal("0.012"), Decimal("0.006")),
        "62": (Decimal("0.24"), Decimal("0.06")),
    },
    "retail": {
        "61": (Decimal("0.11"), Decimal("0.03")),
        "611": (Decimal("0.018"), Decimal("0.008")),
        "62": (Decimal("0.18"), Decimal("0.05")),
    },
    "services": {
        "61": (Decimal("0.16"), Decimal("0.05")),
        "611": (Decimal("0.025"), Decimal("0.012")),
        "62": (Decimal("0.31"), Decimal("0.07")),
    },
    "other": {
        "61": (Decimal("0.14"), Decimal("0.05")),
        "611": (Decimal("0.02"), Decimal("0.01")),
        "62": (Decimal("0.27"), Decimal("0.07")),
    },
}


def _normalize_industry(industry: str | None) -> str:
    raw = (industry or "").strip().lower()
    if not raw:
        return "other"
    if any(token in raw for token in ("software", "saas", "tech")):
        return "technology"
    if any(token in raw for token in ("manufact", "industrial", "factory")):
        return "manufacturing"
    if any(token in raw for token in ("retail", "shop", "store", "ecommerce")):
        return "retail"
    if any(token in raw for token in ("service", "consult", "account", "legal", "agency")):
        return "services"
    return raw if raw in _DEFAULT_BENCHMARKS else "other"


def _normalize_custom_benchmarks(
    sector_benchmarks: dict[str, Any] | None,
) -> dict[str, tuple[Decimal, Decimal]]:
    if not sector_benchmarks:
        return {}

    normalized: dict[str, tuple[Decimal, Decimal]] = {}
    for key, value in sector_benchmarks.items():
        if not isinstance(value, dict):
            continue
        median = value.get("median_pct_revenue", value.get("benchmark_median_pct"))
        std = value.get("std_pct_revenue", value.get("benchmark_std_pct", 0))
        if median is None:
            continue
        normalized[str(key)] = (to_decimal(median), to_decimal(std or 0))
    return normalized


def _resolve_benchmark(
    account_code: str,
    industry: str,
    custom_benchmarks: dict[str, tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal]:
    for prefix in (account_code[:4], account_code[:3], account_code[:2]):
        if prefix in custom_benchmarks:
            return custom_benchmarks[prefix]

    benchmarks = _DEFAULT_BENCHMARKS.get(industry, _DEFAULT_BENCHMARKS["other"])
    for prefix in (account_code[:4], account_code[:3], account_code[:2]):
        if prefix in benchmarks:
            return benchmarks[prefix]
    return benchmarks["61" if account_code.startswith("61") else "62"]


def _suggest_question(account_code: str, description: str) -> str:
    label = description.strip() or f"MAR {account_code}"
    lowered = label.lower()

    if account_code.startswith("611") or any(
        token in lowered for token in ("lease", "leasing", "vehicle", "wagen", "auto")
    ):
        return (
            f"Imported {label}. Is this a personal owner vehicle or lease cost that should "
            "be normalized?"
        )
    if account_code.startswith(("620", "621", "622", "623", "624")) or any(
        token in lowered for token in ("salary", "wage", "remuneration", "bezold", "payroll")
    ):
        return (
            f"Imported {label}. Does this include above-market owner or family remuneration "
            "that should be normalized?"
        )
    if any(token in lowered for token in ("legal", "lawyer", "consult", "advisor", "advisory")):
        return (
            f"Imported {label}. Is this a one-off advisory cost that should be added back?"
        )
    return (
        f"Imported {label}. Is this discretionary or non-recurring spend that should be "
        "normalized?"
    )


def scan_trial_balance_for_sde_flags(
    entries: list[dict[str, Any]],
    *,
    revenue: Decimal | int | float | str | None,
    industry: str | None = None,
    sector_benchmarks: dict[str, Any] | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    revenue_decimal = to_decimal(revenue or 0)
    if revenue_decimal <= 0:
        return []

    normalized_industry = _normalize_industry(industry)
    custom_benchmarks = _normalize_custom_benchmarks(sector_benchmarks)
    flags: list[dict[str, Any]] = []

    for entry in entries:
        account_code = str(entry.get("account_code") or "").strip()
        if not account_code.startswith(("61", "62")):
            continue

        amount = abs(to_decimal(entry.get("balance") or 0))
        if amount <= 0:
            continue

        benchmark_median, benchmark_std = _resolve_benchmark(
            account_code, normalized_industry, custom_benchmarks
        )
        if benchmark_median <= 0:
            continue

        actual_pct = amount / revenue_decimal
        deviation_pct = ((actual_pct - benchmark_median) / benchmark_median) * Decimal("100")
        z_score = (
            (actual_pct - benchmark_median) / benchmark_std
            if benchmark_std > 0
            else Decimal("0")
        )

        exceeds_threshold = (
            actual_pct >= (benchmark_median + benchmark_std)
            and deviation_pct >= Decimal("35")
        ) or z_score >= Decimal("1.5")
        if not exceeds_threshold:
            continue

        confidence = min(
            Decimal("0.95"),
            max(
                Decimal("0.45"),
                Decimal("0.55")
                + (min(deviation_pct, Decimal("150")) / Decimal("300"))
                + (min(z_score, Decimal("3")) / Decimal("15")),
            ),
        )
        description = str(entry.get("description") or "").strip()
        flags.append(
            {
                "ledger_code": account_code,
                "ledger_name": description or f"MAR {account_code}",
                "amount": from_decimal(bank_round(amount)),
                "deviation_pct": from_decimal(bank_round(deviation_pct)),
                "benchmark_median_pct": from_decimal(bank_round(benchmark_median * Decimal("100"))),
                "benchmark_std_pct": from_decimal(bank_round(benchmark_std * Decimal("100"))),
                "actual_pct_of_revenue": from_decimal(bank_round(actual_pct * Decimal("100"))),
                "z_score": from_decimal(bank_round(z_score)),
                "confidence": from_decimal(bank_round(confidence)),
                "year": year,
                "potential_sde_addback": True,
                "suggested_question": _suggest_question(account_code, description),
                "rationale": (
                    f"{account_code} is {from_decimal(bank_round(deviation_pct))}% above the "
                    "sector median as a percentage of revenue."
                ),
                "category": "services_goods" if account_code.startswith("61") else "remuneration",
            }
        )

    flags.sort(key=lambda item: (-(item.get("confidence") or 0), -(item.get("amount") or 0)))
    return flags
