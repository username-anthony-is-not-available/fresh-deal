"""
Deal Export API endpoints.
Allows users to export grocery deals in various formats (CSV, JSON, Markdown)
for use with external LLMs or other tools.
"""

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import case, func
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_async_session
from app.models.all_models import Deal, Product, Store
from app.services.deal_cache_service import deal_cache
from app.services.deal_quality_service import deal_quality_service, DealQuality
from typing import Optional, List
from datetime import datetime, date
import csv
import io

router = APIRouter(prefix="/deals", tags=["deals-export"])

# Approximate CAD value per point for major loyalty programs
LOYALTY_POINT_VALUES = {
    "PC Optimum": 0.001,  # $10 per 10,000 points
    "Scene+": 0.01,  # $10 per 1,000 points
    "Moi": 0.008,  # $1 per 125 points
    "AIR MILES": 0.105,  # Approx. $10 per 95 miles
}


async def get_deals_data(
    session: AsyncSession,
    store: Optional[str] = None,
    category: Optional[str] = None,
    min_discount: Optional[float] = None,
    limit: Optional[int] = None,
    active_only: bool = False,
) -> List[dict]:
    """Fetch deals with optional SQL-level filtering, sorting, limit, and TTL cache."""
    async def _load() -> List[dict]:
        statement = select(Deal, Product, Store).join(Product).join(Store)

        if active_only:
            today = date.today()
            statement = statement.where(Deal.valid_from <= today, Deal.valid_until >= today)
        if store:
            statement = statement.where(Store.chain.ilike(f"%{store}%"))
        if category:
            statement = statement.where(Product.category.ilike(f"%{category}%"))
        if min_discount:
            statement = statement.where(Deal.discount_pct >= min_discount)

        # Push discount sorting and row cap directly to SQL
        statement = statement.order_by(func.coalesce(Deal.discount_pct, 0).desc())
        if limit is not None:
            statement = statement.limit(limit)

        result = await session.execute(statement)
        results = result.all()

        deals_data = []
        for deal, product, store_obj in results:
            effective_price = deal.price
            loyalty_value = 0.0
            if deal.loyalty_program and deal.loyalty_points:
                point_value = LOYALTY_POINT_VALUES.get(deal.loyalty_program, 0)
                loyalty_value = deal.loyalty_points * point_value
                effective_price -= loyalty_value

            savings = 0.0
            if deal.original_price and deal.original_price > deal.price:
                savings = deal.original_price - deal.price

            deals_data.append(
                {
                    "product_name": product.name,
                    "category": product.category,
                    "store": store_obj.chain,
                    "store_location": store_obj.name,
                    "price": deal.price,
                    "original_price": deal.original_price or deal.price,
                    "discount_pct": deal.discount_pct or 0,
                    "savings": round(savings, 2),
                    "unit": product.unit_type,
                    "valid_from": str(deal.valid_from) if deal.valid_from else None,
                    "valid_until": str(deal.valid_until) if deal.valid_until else None,
                    "loyalty_program": deal.loyalty_program,
                    "loyalty_points": deal.loyalty_points,
                    "loyalty_value": round(loyalty_value, 2),
                    "effective_price": round(effective_price, 2),
                    "quality_score": deal.quality_score,
                    "quality_level": deal.quality_level,
                    "sale_info": deal.sale_info or "",
                }
            )
        return deals_data

    return await deal_cache.get_or_set_async(
        "export:deals_data",
        _load,
        store=store,
        category=category,
        min_discount=min_discount,
        limit=limit,
        active_only=active_only,
    )


@router.get("/export")
async def export_deals(
    output_format: str = Query(
        "json", enum=["json", "csv", "markdown", "text"], alias="format"
    ),
    store: Optional[str] = Query(
        None, description="Filter by store chain (e.g., Metro, IGA)"
    ),
    category: Optional[str] = Query(
        None, description="Filter by category (e.g., Meat, Dairy)"
    ),
    min_discount: Optional[float] = Query(
        None, description="Minimum discount percentage"
    ),
    limit: Optional[int] = Query(None, description="Maximum number of deals to return"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Export grocery deals in various formats.

    Formats:
    - **json**: Structured JSON array (default)
    - **csv**: Comma-separated values for spreadsheets
    - **markdown**: Markdown table for documentation/LLMs
    - **text**: Plain text list optimized for LLM consumption

    This endpoint is designed to provide structured deal data that can be
    passed to LLMs for meal planning, as requested by the Quebec tech community.
    """
    deals = await get_deals_data(session, store, category, min_discount, limit)

    if output_format == "json":
        return JSONResponse(content=deals)

    elif output_format == "csv":
        output = io.StringIO()
        if deals:
            writer = csv.DictWriter(output, fieldnames=deals[0].keys())
            writer.writeheader()
            writer.writerows(deals)

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=deals_{date.today()}.csv"
            },
        )

    elif output_format == "markdown":
        md_content = generate_markdown_table(deals)
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=deals_{date.today()}.md"
            },
        )

    elif output_format == "text":
        text_content = generate_llm_text(deals)
        return Response(
            content=text_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=deals_{date.today()}.txt"
            },
        )


@router.get("/best")
async def get_best_deals(
    limit: int = Query(20, description="Number of top deals to return"),
    store: Optional[str] = Query(None, description="Filter by store chain"),
    category: Optional[str] = Query(None, description="Filter by category"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get the best current deals ranked by effective discount.

    This endpoint mimics the "Meilleurs rabais" feature from circulaire-en-ligne.ca,
    returning only the top deals sorted by savings percentage.

    Considers both price discounts and loyalty point values when ranking.
    """
    candidate_limit = max(limit * 5, 100) if limit is not None else None
    deals = await get_deals_data(
        session, store, category, min_discount=5.0, limit=candidate_limit
    )

    # Calculate a "deal score" that considers both discount % and loyalty value
    for deal in deals:
        base_score = deal["discount_pct"]
        # Add bonus for loyalty points (up to 10% boost)
        if deal["loyalty_value"] > 0 and deal["original_price"] > 0:
            loyalty_bonus = (deal["loyalty_value"] / deal["original_price"]) * 100
            base_score += min(loyalty_bonus, 10)
        deal["deal_score"] = round(base_score, 1)

    # Sort by deal score
    deals.sort(key=lambda x: x["deal_score"], reverse=True)

    return {
        "generated_at": datetime.now().isoformat(),
        "total_deals": len(deals[:limit]),
        "best_deals": deals[:limit],
    }


@router.get("/summary")
async def get_weekly_summary(
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get a weekly summary of deals by store and category using SQL GROUP BY aggregations
    and server-side caching.
    """
    async def _compute_summary() -> dict:
        savings_expr = case(
            (
                (Deal.original_price.is_not(None)) & (Deal.original_price > Deal.price),
                Deal.original_price - Deal.price,
            ),
            else_=0.0,
        )
        discount_expr = func.coalesce(Deal.discount_pct, 0.0)

        store_rows = (
            await session.execute(
                select(
                    Store.chain,
                    func.count(Deal.id),
                    func.sum(savings_expr),
                    func.avg(discount_expr),
                )
                .select_from(Deal)
                .join(Store, Deal.store_id == Store.id)
                .group_by(Store.chain)
            )
        ).all()

        if not store_rows:
            return {"message": "No deals available", "summary": {}}

        store_cats_rows = (
            await session.execute(
                select(Store.chain, Product.category)
                .select_from(Deal)
                .join(Store, Deal.store_id == Store.id)
                .join(Product, Deal.product_id == Product.id)
                .distinct()
            )
        ).all()
        cats_by_store: dict[str, list[str]] = {}
        for store_chain, cat in store_cats_rows:
            cats_by_store.setdefault(store_chain, []).append(cat)

        stores_summary = {}
        total_deals = 0
        for store_chain, deal_count, total_savings, avg_discount in store_rows:
            count = int(deal_count or 0)
            total_deals += count
            stores_summary[store_chain] = {
                "deal_count": count,
                "total_savings": round(float(total_savings or 0.0), 2),
                "avg_discount": round(float(avg_discount or 0.0), 1),
                "categories": cats_by_store.get(store_chain, []),
            }

        category_rows = (
            await session.execute(
                select(
                    Product.category,
                    func.count(Deal.id),
                    func.avg(discount_expr),
                )
                .select_from(Deal)
                .join(Product, Deal.product_id == Product.id)
                .group_by(Product.category)
            )
        ).all()

        categories_summary = {}
        for cat_name, deal_count, avg_discount in category_rows:
            categories_summary[cat_name] = {
                "deal_count": int(deal_count or 0),
                "avg_discount": round(float(avg_discount or 0.0), 1),
            }

        top_categories = sorted(
            categories_summary.items(), key=lambda x: x[1]["avg_discount"], reverse=True
        )[:5]

        return {
            "generated_at": datetime.now().isoformat(),
            "total_deals": total_deals,
            "stores": stores_summary,
            "categories": categories_summary,
            "top_categories": [{"name": c[0], **c[1]} for c in top_categories],
        }

    return await deal_cache.get_or_set_async("export:weekly_summary", _compute_summary)


def generate_markdown_table(deals: List[dict]) -> str:
    """Generate a markdown table from deals data."""
    if not deals:
        return "# Aucun rabais disponible / No deals available\n"

    lines = [
        f"# Rabais d'épicerie - {date.today()}",
        f"# Grocery Deals - {date.today()}",
        "",
        f"*{len(deals)} deals found*",
        "",
        "| Produit | Magasin | Prix | Prix orig. | Rabais | Unité |",
        "|---------|---------|------|------------|--------|-------|",
    ]

    for deal in deals:
        discount_str = f"{deal['discount_pct']:.0f}%" if deal["discount_pct"] else "-"
        lines.append(
            f"| {deal['product_name'][:30]} | {deal['store']} | "
            f"${deal['price']:.2f} | ${deal['original_price']:.2f} | "
            f"{discount_str} | {deal['unit']} |"
        )

    return "\n".join(lines)


def generate_llm_text(deals: List[dict]) -> str:
    """
    Generate plain text optimized for LLM consumption.
    This format is designed to be easily parsed by AI for meal planning.
    """
    if not deals:
        return "No grocery deals available this week."

    lines = [
        f"GROCERY DEALS - Week of {date.today()}",
        f"Total: {len(deals)} deals",
        "=" * 50,
        "",
    ]

    # Group by store
    stores = {}
    for deal in deals:
        store = deal["store"]
        if store not in stores:
            stores[store] = []
        stores[store].append(deal)

    for store, store_deals in stores.items():
        lines.append(f"\n## {store.upper()}")
        lines.append("-" * 30)

        for deal in store_deals:
            discount_str = (
                f"({deal['discount_pct']:.0f}% off)" if deal["discount_pct"] else ""
            )
            loyalty_str = ""
            if deal["loyalty_points"]:
                loyalty_str = (
                    f" + {deal['loyalty_points']} {deal['loyalty_program']} pts"
                )

            lines.append(
                f"- {deal['product_name']}: ${deal['price']:.2f}/{deal['unit']} "
                f"{discount_str}{loyalty_str}"
            )

    lines.extend(
        [
            "",
            "=" * 50,
            "Data source: Smart Meal Planner Deal Aggregator",
            f"Generated: {datetime.now().isoformat()}",
        ]
    )

    return "\n".join(lines)


@router.get("/quality")
async def get_deals_with_quality(
    min_quality: str = Query(
        "average", enum=["excellent", "good", "average", "poor", "noise"]
    ),
    store: Optional[str] = Query(None, description="Filter by store chain"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: Optional[int] = Query(50, description="Maximum number of deals"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get deals filtered and scored by quality.

    This endpoint uses the Deal Quality Service to:
    - Filter out marketing noise and fake discounts
    - Score deals based on actual savings value
    - Remove perpetual "sale" items that are always discounted

    Quality levels:
    - **excellent**: 30%+ real discount, no marketing noise
    - **good**: 20-30% discount, minor issues
    - **average**: 10-20% discount
    - **poor**: <10% discount or suspicious pricing
    - **noise**: Marketing gimmicks, not real deals

    Based on Reddit r/QuebecTI feedback about filtering "Watatow" marketing noise.
    """
    deals = await get_deals_data(session, store, category, limit=None)

    # Map string to enum
    quality_map = {
        "excellent": DealQuality.EXCELLENT,
        "good": DealQuality.GOOD,
        "average": DealQuality.AVERAGE,
        "poor": DealQuality.POOR,
        "noise": DealQuality.NOISE,
    }
    min_q = quality_map.get(min_quality, DealQuality.AVERAGE)

    # Convert deals to format expected by quality service
    deals_for_scoring = []
    for deal in deals:
        deals_for_scoring.append(
            {
                "name": deal["product_name"],
                "price": deal["price"],
                "original_price": deal["original_price"],
                "discount_pct": deal["discount_pct"],
                "category": deal["category"],
                "store": deal["store"],
                "loyalty_points": deal["loyalty_points"],
                "loyalty_program": deal["loyalty_program"],
                "sale_info": deal.get("sale_info", ""),
            }
        )

    # Filter by quality
    filtered_deals = deal_quality_service.filter_deals(
        deals_for_scoring, min_quality=min_q
    )

    # Merge quality info back into original deal format
    result = []
    for scored_deal in filtered_deals[:limit]:
        result.append(
            {
                "product_name": scored_deal["name"],
                "category": scored_deal["category"],
                "store": scored_deal["store"],
                "price": scored_deal["price"],
                "original_price": scored_deal["original_price"],
                "discount_pct": scored_deal["discount_pct"],
                "loyalty_points": scored_deal.get("loyalty_points"),
                "loyalty_program": scored_deal.get("loyalty_program"),
                "quality_score": scored_deal.get("quality_score"),
                "quality_level": scored_deal.get("quality_level"),
                "quality_flags": scored_deal.get("quality_flags", []),
            }
        )

    return {
        "filter_applied": min_quality,
        "total_before_filter": len(deals),
        "total_after_filter": len(result),
        "deals": result,
    }


@router.get("/quality/summary")
async def get_quality_summary(
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get a summary of deal quality across all current deals.

    Returns statistics on:
    - Quality distribution (how many excellent/good/average/poor/noise deals)
    - Common quality issues detected
    - Recommendations for best shopping
    """
    deals = await get_deals_data(session)

    # Convert to scoring format
    deals_for_scoring = [
        {
            "name": d["product_name"],
            "price": d["price"],
            "original_price": d["original_price"],
            "discount_pct": d["discount_pct"],
            "category": d["category"],
            "store": d["store"],
            "loyalty_points": d["loyalty_points"],
            "loyalty_program": d["loyalty_program"],
            "sale_info": "",
        }
        for d in deals
    ]

    summary = deal_quality_service.get_quality_summary(deals_for_scoring)

    # Add recommendations
    recommendations = []
    if summary["excellent_deals"] > 0:
        recommendations.append(
            f"🎯 {summary['excellent_deals']} excellent deals available - check these first!"
        )
    if summary["noise_filtered"] > 5:
        recommendations.append(
            f"⚠️ {summary['noise_filtered']} deals filtered as marketing noise"
        )
    if summary["average_score"] < 50:
        recommendations.append(
            "📉 Average deal quality is low this week - consider waiting for better sales"
        )
    elif summary["average_score"] > 70:
        recommendations.append("📈 Great week for deals! Average quality is high")

    summary["recommendations"] = recommendations
    summary["generated_at"] = datetime.now().isoformat()

    return summary
