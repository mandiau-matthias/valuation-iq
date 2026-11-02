"""Asset deal vs. share deal comparison engine.

Belgian SME M&A practice distinguishes two transaction structures:

  1. **Aandelen / Share deal** — buyer acquires the legal entity. Latent
     liabilities transfer; no fiscal step-up; for a private individual
     seller a flat 10% capital gains tax applies from 01/01/2026
     (Art. 90 / 95 WIB 92, "meerwaardebelasting").

  2. **Handelsfonds / Asset deal** — buyer acquires the goodwill and
     assets. Buyer obtains a **fiscal step-up**: goodwill is amortisable
     over 5 years (Art. 61 WIB 92), generating a tax-shield NPV. Seller
     realises a corporate-level meerwaarde taxed at the standard CIT
     rate (default 25%).

This module computes the indifference price, the buyer's tax shield NPV,
and the seller-side after-tax proceeds for both structures so an advisor
can articulate the price delta defensibly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Optional

from src.config.belgian_tax import (
    ASSET_DEAL_GOODWILL_GAIN_RATE,
    GOODWILL_AMORTISATION_YEARS,
    PRIVATE_SHARE_CAPITAL_GAINS_RATE,
    SmeEligibility,
    resolve_corporate_tax_rate,
)


@dataclass(frozen=True)
class DealStructureScenario:
    label: str
    headline_price: Decimal
    seller_tax: Decimal
    seller_net_proceeds: Decimal
    buyer_tax_shield_npv: Decimal
    buyer_net_cost: Decimal
    notes: tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "headline_price": float(self.headline_price),
            "seller_tax": float(self.seller_tax),
            "seller_net_proceeds": float(self.seller_net_proceeds),
            "buyer_tax_shield_npv": float(self.buyer_tax_shield_npv),
            "buyer_net_cost": float(self.buyer_net_cost),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class DealStructureComparison:
    share_deal: DealStructureScenario
    asset_deal: DealStructureScenario
    indifference_premium: Decimal
    recommendation: str
    inputs_echo: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "share_deal": self.share_deal.to_dict(),
            "asset_deal": self.asset_deal.to_dict(),
            "indifference_premium": float(self.indifference_premium),
            "recommendation": self.recommendation,
            "inputs": self.inputs_echo,
        }


def _present_value_of_amortisation(
    *,
    goodwill: Decimal,
    buyer_cit_rate_pct: Decimal,
    discount_rate_pct: Decimal,
    years: int = GOODWILL_AMORTISATION_YEARS,
) -> Decimal:
    """NPV of the tax shield from straight-line goodwill amortisation.

    Tax shield each year = (goodwill / years) * (CIT% / 100).
    Discounted at end-of-year for `years` periods.
    """
    if goodwill <= 0 or years <= 0:
        return Decimal("0")
    annual_amortisation = goodwill / Decimal(years)
    annual_shield = annual_amortisation * buyer_cit_rate_pct / Decimal("100")
    discount = Decimal("1") + (discount_rate_pct / Decimal("100"))
    if discount <= 0:
        discount = Decimal("1")
    pv = Decimal("0")
    factor = Decimal("1")
    for _ in range(int(years)):
        factor = factor * discount
        pv += annual_shield / factor
    return pv.quantize(Decimal("0.01"))


def compare_deal_structures(
    *,
    headline_equity_value: Decimal,
    book_equity: Decimal,
    goodwill_in_asset_deal: Optional[Decimal] = None,
    seller_share_basis: Optional[Decimal] = None,
    seller_is_individual: bool = True,
    buyer_discount_rate_pct: Decimal = Decimal("10"),
    country_code: str = "BE",
    taxable_profit: Optional[Decimal] = None,
    director_remuneration: Optional[Decimal] = None,
    sme_rate_override: Optional[bool] = None,
    registration_duty_pct: Decimal = Decimal("0"),
) -> DealStructureComparison:
    """Compute the buyer/seller economics for both deal structures.

    Args:
        headline_equity_value: Indicative equity value (the "sticker price")
            both sides start from. Used as the share-deal proceeds.
        book_equity: Statutory book equity (used to derive the implicit
            goodwill in an asset deal when one is not supplied).
        goodwill_in_asset_deal: Buyer-paid goodwill in the asset deal. If
            omitted, defaults to ``max(0, headline_equity_value - book_equity)``
            which is the implicit goodwill assuming the asset deal price
            equals the share-deal headline.
        seller_share_basis: Seller's tax basis in the shares (cost). Used
            in the share-deal capital-gains computation. Defaults to 0.
        seller_is_individual: If True, the share deal is modelled with the
            private capital-gains scenario (Art. 90 WIB 92; rate and
            applicability to be confirmed). If False, the seller is a holding
            company and a DBI/participation-exemption analysis is referenced
            in notes.
        buyer_discount_rate_pct: Discount rate used to compute the tax
            shield NPV from goodwill amortisation. Defaults to 10%.
        registration_duty_pct: Estimated registration duty on movables in
            an asset deal (regional). Subtracted from buyer net cost.
    """
    eligibility: SmeEligibility = resolve_corporate_tax_rate(
        country_code=country_code,
        taxable_profit=taxable_profit,
        director_remuneration=director_remuneration,
        explicit_override=sme_rate_override,
    )
    buyer_cit_rate = eligibility.rate

    # ---- Share deal -------------------------------------------------------
    share_basis = seller_share_basis if seller_share_basis is not None else Decimal("0")
    share_capital_gain = max(Decimal("0"), headline_equity_value - share_basis)

    if seller_is_individual and country_code.upper() == "BE":
        share_seller_tax = (
            share_capital_gain * PRIVATE_SHARE_CAPITAL_GAINS_RATE / Decimal("100")
        ).quantize(Decimal("0.01"))
        share_notes = (
            "Private capital-gains tax scenario (Art. 90 WIB 92) — rate and conditions to be confirmed with a tax advisor.",
            "Buyer inherits all latent liabilities; no fiscal step-up.",
            "No goodwill amortisation tax shield available to buyer.",
        )
    elif country_code.upper() == "BE":
        share_seller_tax = Decimal("0")
        share_notes = (
            "Corporate seller — DBI/participation exemption likely (95%+ exempt).",
            "Confirm 1-year holding period and minimum-taxation conditions.",
        )
    else:
        share_seller_tax = Decimal("0")
        share_notes = ("Non-Belgian regime — confirm local rules.",)

    share_deal = DealStructureScenario(
        label="Aandelen (Share Deal)",
        headline_price=headline_equity_value,
        seller_tax=share_seller_tax,
        seller_net_proceeds=(headline_equity_value - share_seller_tax).quantize(
            Decimal("0.01")
        ),
        buyer_tax_shield_npv=Decimal("0"),
        buyer_net_cost=headline_equity_value,
        notes=share_notes,
    )

    # ---- Asset deal -------------------------------------------------------
    if goodwill_in_asset_deal is None:
        goodwill_in_asset_deal = max(
            Decimal("0"), headline_equity_value - book_equity
        )

    # Seller realises the goodwill at corporate level — taxed at CIT rate.
    asset_seller_gain = goodwill_in_asset_deal
    asset_seller_tax = (
        asset_seller_gain * ASSET_DEAL_GOODWILL_GAIN_RATE / Decimal("100")
    ).quantize(Decimal("0.01"))

    buyer_tax_shield_npv = _present_value_of_amortisation(
        goodwill=goodwill_in_asset_deal,
        buyer_cit_rate_pct=buyer_cit_rate,
        discount_rate_pct=buyer_discount_rate_pct,
    )

    registration_duty = (
        headline_equity_value * registration_duty_pct / Decimal("100")
    ).quantize(Decimal("0.01"))

    # Asset deal headline price: assume buyer is willing to pay up to the
    # share-deal price; seller would prefer to be made whole on the after-tax
    # delta. The "fair" indifference logic is exposed via indifference_premium
    # below — the headline here is the same nominal price for comparability.
    asset_deal_headline = headline_equity_value

    asset_deal = DealStructureScenario(
        label="Handelsfonds (Asset Deal)",
        headline_price=asset_deal_headline,
        seller_tax=asset_seller_tax,
        seller_net_proceeds=(
            asset_deal_headline - asset_seller_tax
        ).quantize(Decimal("0.01")),
        buyer_tax_shield_npv=buyer_tax_shield_npv,
        buyer_net_cost=(
            asset_deal_headline - buyer_tax_shield_npv + registration_duty
        ).quantize(Decimal("0.01")),
        notes=(
            f"Goodwill EUR {float(goodwill_in_asset_deal):,.0f} amortised "
            f"over {GOODWILL_AMORTISATION_YEARS} years (Art. 61 WIB 92).",
            f"Buyer CIT rate {float(buyer_cit_rate):.2f}% — flat valuation assumption.",
            "Tax-shield scenario assumes full annual deductibility and sufficient buyer taxable profit; utilisation is not evidenced.",
            "Latent liabilities remain with the seller's legal entity.",
            f"Registration duties: {float(registration_duty_pct):.1f}% on "
            "movables (regional).",
        ),
    )

    # ---- Indifference premium --------------------------------------------
    # The premium an asset-deal seller would need to be paid above the share
    # deal price to be indifferent on after-tax proceeds.
    seller_delta = share_deal.seller_net_proceeds - asset_deal.seller_net_proceeds
    indifference_premium = max(Decimal("0"), seller_delta).quantize(Decimal("0.01"))

    if asset_deal.buyer_net_cost < share_deal.buyer_net_cost:
        recommendation = (
            "Asset deal is cheaper for the buyer net of the goodwill tax "
            "shield. A premium up to the buyer's saving can be split with "
            "the seller to align both sides."
        )
    else:
        recommendation = (
            "Share deal is more efficient for both sides under these inputs. "
            "Re-test if goodwill > book equity grows materially."
        )

    return DealStructureComparison(
        share_deal=share_deal,
        asset_deal=asset_deal,
        indifference_premium=indifference_premium,
        recommendation=recommendation,
        inputs_echo={
            "buyer_cit_rate_pct": float(buyer_cit_rate),
            "buyer_discount_rate_pct": float(buyer_discount_rate_pct),
            "goodwill_in_asset_deal": float(goodwill_in_asset_deal),
            "registration_duty_pct": float(registration_duty_pct),
            "seller_is_individual": seller_is_individual,
            "sme_eligibility": eligibility.to_dict(),
        },
    )


__all__ = [
    "DealStructureScenario",
    "DealStructureComparison",
    "compare_deal_structures",
]
