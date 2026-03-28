
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import Deal, Store
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.services.deal_quality_service import deal_quality_service

class DealService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_deals_as_dicts(self) -> List[Dict[str, Any]]:
        """
        Fetches all active deals and returns them as a list of dictionaries,
        enriched with product and store information.
        """
        today = datetime.now(timezone.utc).date()

        statement = (
            select(Deal)
            .options(
                selectinload(Deal.product),
                selectinload(Deal.store)
            )
            .where(Deal.valid_from <= today, Deal.valid_until >= today)
        )

        result = await self.session.execute(statement)
        deals = result.scalars().unique().all()

        deals_list = []
        for deal in deals:
            if deal.product and deal.store:
                deal_dict = {
                    "product": deal.product.name,
                    "store": deal.store.name,
                    "category": deal.product.category,
                    "price": deal.price,
                    "regular_price": deal.original_price,
                    "discount_percent": deal.discount_pct,
                    "expires_in_days": (deal.valid_until - today).days,
                    "unit": deal.product.unit_type,
                }
                deals_list.append(deal_dict)

        return deals_list

    async def get_top_deals(self, limit: int = 10, postal_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches top ranked deals based on quality and discount.
        Optionally filters by the first 3 characters of the postal code (Forward Sortation Area).
        """
        today = datetime.now(timezone.utc).date()

        statement = (
            select(Deal)
            .options(
                selectinload(Deal.product),
                selectinload(Deal.store)
            )
            .where(Deal.valid_from <= today, Deal.valid_until >= today)
        )

        if postal_code:
            fsa = postal_code[:3].upper()
            statement = statement.join(Store).where(Store.postal_code.like(f"{fsa}%"))

        result = await self.session.execute(statement)
        deals = result.scalars().unique().all()

        deals_dicts = []
        for deal in deals:
            if deal.product and deal.store:
                d = {
                    "product": deal.product.name,
                    "store": deal.store.name,
                    "category": deal.product.category,
                    "price": deal.price,
                    "original_price": deal.original_price,
                    "discount_pct": deal.discount_pct,
                    "unit": deal.product.unit_type,
                    "image_url": deal.image_url,
                    "sale_info": deal.sale_info,
                    "loyalty_program": deal.loyalty_program,
                    "loyalty_points": deal.loyalty_points
                }
                deals_dicts.append(d)

        # Use deal_quality_service to rank and limit
        top_deals = deal_quality_service.rank_deals(deals_dicts, top_n=limit)

        return top_deals
