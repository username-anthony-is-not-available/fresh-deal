
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import Deal, Product, Store
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any
from datetime import datetime, timezone

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
