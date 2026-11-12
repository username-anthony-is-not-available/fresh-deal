import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import func
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import Deal, Product, Store
from app.services.deal_quality_service import deal_quality_service


def _calc_loyalty_and_effective(price: float, program: Optional[str], points: Optional[int], sale_info: Optional[str] = None):
    point_values = {
        "pc optimum": 0.001,
        "optimum": 0.001,
        "scene+": 0.01,
        "scene": 0.01,
        "moi": 0.008,
        "air miles": 0.105,
    }
    loyalty_savings = 0.0
    effective_price = price
    is_member_price = False

    if points and points > 0 and program:
        for k, v in point_values.items():
            if k in program.lower():
                loyalty_savings += points * v
                break

    if sale_info:
        m = re.search(r"(?:member|membre)[^\d]*(\d+(?:[.,]\d{2})?)", sale_info, re.IGNORECASE)
        if m:
            mem_val = float(m.group(1).replace(",", "."))
            if mem_val < price:
                is_member_price = True
                loyalty_savings += (price - mem_val)
                effective_price = mem_val

    if not is_member_price and loyalty_savings > 0:
        effective_price = max(0.01, effective_price - loyalty_savings)

    return round(effective_price, 2), round(loyalty_savings, 2), is_member_price


class DealService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_deals_as_dicts(self) -> List[Dict[str, Any]]:
        """
        Fetches active deals and converts them to dictionaries for LLM and planning context
        using a single SQL JOIN query instead of separate selectinload roundtrips.
        """
        today = datetime.now(timezone.utc).date()

        statement = (
            select(Deal, Product, Store)
            .join(Product, Deal.product_id == Product.id)
            .join(Store, Deal.store_id == Store.id)
            .where(Deal.valid_from <= today, Deal.valid_until >= today)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        deals_list = []
        for deal, product, store in rows:
            eff_p, loy_sav, is_mem = _calc_loyalty_and_effective(
                deal.price, deal.loyalty_program, deal.loyalty_points, deal.sale_info
            )
            deals_list.append({
                "product": product.name,
                "store": store.name,
                "category": product.category,
                "price": deal.price,
                "effective_price": eff_p,
                "loyalty_savings_cad": loy_sav,
                "is_member_price": is_mem,
                "regular_price": deal.original_price,
                "discount_percent": deal.discount_pct,
                "expires_in_days": (deal.valid_until - today).days,
                "unit": product.unit_type,
                "loyalty_program": deal.loyalty_program,
                "loyalty_points": deal.loyalty_points,
                "sale_info": deal.sale_info,
            })

        return deals_list

    async def get_top_deals(self, limit: int = 10, postal_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches top ranked deals based on quality, effective savings, and discount.
        Optionally filters by the first 3 characters of the postal code (Forward Sortation Area).
        """
        today = datetime.now(timezone.utc).date()
        candidate_limit = max(limit * 5, 50)

        statement = (
            select(Deal, Product, Store)
            .join(Product, Deal.product_id == Product.id)
            .join(Store, Deal.store_id == Store.id)
            .where(Deal.valid_from <= today, Deal.valid_until >= today)
            .order_by(
                func.coalesce(Deal.quality_score, 0).desc(),
                func.coalesce(Deal.discount_pct, 0).desc(),
            )
            .limit(candidate_limit)
        )

        if postal_code:
            fsa = postal_code[:3].upper()
            statement = statement.where(Store.postal_code.like(f"{fsa}%"))

        result = await self.session.execute(statement)
        rows = result.all()

        deals_dicts = []
        for deal, product, store in rows:
            eff_p, loy_sav, is_mem = _calc_loyalty_and_effective(
                deal.price, deal.loyalty_program, deal.loyalty_points, deal.sale_info
            )
            deals_dicts.append({
                "product": product.name,
                "store": store.name,
                "category": product.category,
                "price": deal.price,
                "effective_price": eff_p,
                "loyalty_savings_cad": loy_sav,
                "is_member_price": is_mem,
                "original_price": deal.original_price,
                "discount_pct": deal.discount_pct,
                "unit": product.unit_type,
                "image_url": deal.image_url,
                "sale_info": deal.sale_info,
                "loyalty_program": deal.loyalty_program,
                "loyalty_points": deal.loyalty_points,
            })

        top_deals = deal_quality_service.rank_deals(deals_dicts, top_n=limit)
        return top_deals
